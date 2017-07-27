from utils.batch_utils import Batch_Loader
import tensorflow as tf
import numpy as np
import datetime

class Model(object):
	def __init__(self, n_entities, n_relations, hparams):
		self.n_entities = n_entities
		self.n_relations = n_relations

		# required params
		self.embedding_size = hparams.embedding_size
		self.lr = hparams.lr
		self.batch_size = hparams.batch_size
		self.max_iter = hparams.max_iter
		self.neg_ratio = hparams.neg_ratio
		self.contiguous_sampling = hparams.contiguous_sampling
		self.valid_every = hparams.valid_every

		# global step for tensorflow
		self.global_step = tf.Variable(0, name="global_step", trainable=False)

	def add_placeholders(self):
		self.heads = tf.placeholder(tf.int32, [None], name="head_entities")
		self.tails = tf.placeholder(tf.int32, [None], name="tail_entities")
		self.relations = tf.placeholder(tf.int32, [None], name="relations")
		self.labels = tf.placeholder(tf.float32, [None], name="labels")
	
	def create_feed_dict(self, heads, relations, tails, labels=None):
		feed_dict = {
			self.heads: heads,
			self.relations: relations,
			self.tails: tails,
		}
		if labels is not None:
			feed_dict[self.labels] = labels
		return feed_dict

	def add_params(self):
		"""
		Define the variables in Tensorflow for params in the model.
		"""
		raise NotImplementedError("Each Model must re-implement this method.")

	def add_prediction_op(self):
		"""
		Define the prediction operator: self.pred
		"""
		raise NotImplementedError("Each Model must re-implement this method.")

	def add_loss_op(self):
		"""
		Define the loss operator: self.loss
		"""
		raise NotImplementedError("Each Model must re-implement this method.")

	def add_training_op(self):
		"""
		Define the training operator: self.train_op
		"""
		raise NotImplementedError("Each Model must re-implement this method.")

	def train_on_batch(self, sess, input_batch):
		feed = self.create_feed_dict(**input_batch)
		_, step, loss = sess.run([self.train_op, self.global_step, self.loss], feed_dict=feed)
		time_str = datetime.datetime.now().isoformat()
		print("{}: step {}, loss {:g}".format(time_str, step, loss))
	
	def predict(self, sess, test_triples):
		test_batch_loader = Batch_Loader(test_triples, self.n_entities, batch_size=5000, neg_ratio=0, contiguous_sampling=True)
		preds = []
		for i in range(len(test_triples)//5000 + 1):
			input_batch = test_batch_loader()
			feed = self.create_feed_dict(**input_batch)
			pred = sess.run(self.pred, feed_dict=feed)
			preds = np.concatenate([preds, pred])
		return preds

	def fit(self, sess, train_triples, valid_triples=None, scorer=None):
		train_batch_loader = Batch_Loader(train_triples, self.n_entities, batch_size=self.batch_size, neg_ratio=self.neg_ratio, contiguous_sampling=self.contiguous_sampling)
		def pred_func(test_triples):
			return self.predict(sess, test_triples)

		best_step = -1
		best_mrr = -1
		for i in range(self.max_iter):
			input_batch = train_batch_loader()
			self.train_on_batch(sess, input_batch)
			current_step = tf.train.global_step(sess, self.global_step)
			if (current_step % self.valid_every == 0) and (valid_triples is not None):
				print("\nValidation:")
				res = scorer.compute_scores(pred_func, valid_triples)
				print("raw mrr {:g}, filtered mrr {:g}".format(res.raw_mrr, res.mrr))
				if best_mrr >= res.mrr:
					print("Validation filtered MRR decreased, stopping here!")
					break
				else:
					best_mrr = res.mrr
					best_step = current_step
				print("")
		return best_step, best_mrr
	
	def build(self):
		self.add_placeholders()
		self.add_params()
		self.add_prediction_op()
		self.add_loss_op()
		self.add_training_op()