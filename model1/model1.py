# model1.py

'''
The baseline model.
Using nltk package to generate a language model for prediction.
This is a very simple model to generate a baseline.
n = {2,3,4} will be the hyperparameter set we choose, based on Rada's advice
'''

from pathlib import Path
from operator import itemgetter
import json, sys, shutil, os
import numpy as np
import nltk
from gensim.models import Word2Vec
import gensim.models.keyedvectors as word2vec
from model1_config import model1_params
from nltk.util import ngrams
from collections import Counter
import pygtrie as trie
import heapq, copy

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from system_config import system_params
from prep_data import get_review_data, get_word_embedding

os.environ["TF_CPP_MIN_LOG_LEVEL"]="3"

class word_prob(object):
    '''
    Simply a wrapper that includes a word and its probability.
    '''
    def __init__(self, word, prob):
        self.word = word
        self.prob = prob

    def __eq__(self, other):
        if self.prob == other.prob:
            return True
        return False

    def __lt__(self, other):
        if self.prob < other.prob:
            return True
        return False

    def __gt__(self, other):
        if self.prob > other.prob:
            return True
        return False

    def __le__(self, other):
        if self.prob <= other.prob:
            return True
        return False

    def __ge__(self, other):
        if self.prob >= other.prob:
            return True
        return False

class Language_Model(object):
    '''
    A language model that holds the training data and generates prediction
    '''
    def __init__(self,
                 ngrams,
                 n,
                 voc_set,
                 smoothing='add_one'):
        assert(smoothing is None or smoothing == 'add_one')
        self.ngrams = Counter(ngrams)
        self.n = n
        self.smoothing = smoothing
        self.voc_set = voc_set
        self.num_voc = len(voc_set)
        self.voc_list = list(voc_set)
        self.pred_dict = {}
    
    def predict(self, prev_words, topn=10):
        '''
        Generate topn predictions given the prev_words.
        Input:
            prev_words: a list of strings, each of string is a word
            topn: number of words that should be returned
        Output:
            a list of words, in decending order of their probability to appear
            given prev_words
        '''

        h = []
        # Optimization using DP
        if prev_words in self.pred_dict:
            return self.pred_dict[prev_words]
        prev_words = list(prev_words)
        prev_words.append("")
        for word in self.voc_list:
            prev_words[-1] = word
            temp = tuple(prev_words)
            if self.smoothing == 'add_one':
                prob = (self.ngrams[temp] + 1) / (self.voc_set[word] + self.num_voc)
            else:
                prob = (self.ngrams[temp]) / (self.voc_set[word])
            w_p = word_prob(word, prob)
            h.append(w_p)
        heapq.heapify(h)
        top_wp = heapq.nlargest(topn, h)
        prediction = [wp.word for wp in top_wp]
        self.pred_dict[tuple(prev_words[0:-1])]=prediction
        return prediction

def sentence_concat(sentences):
    '''
    This is a helper function that concat a list of sentences into one sentence.
    Input: 
        sentences, which is a list of list of strings, each string represents a word
    Output:
        sentences, which is a list of strings, each string represents a word
    '''
    temp = []
    for sentence in sentences:
        temp += sentence
    return temp    

def ngram_train(filename, start_train, end_train, n):
    '''
    Generates the language model with the given parameters.
    Input:
        filename: a string of location of corpus
        start_train, end_train: start and end index
        n: hyperparameter
    Output:
        a language model instance
    '''
    print('training the model')
    train_sentences, stars = get_review_data(filename, start_train, end_train)
    train_sentences = [sentence[5:] for sentence in train_sentences]
    train_sentences = sentence_concat(train_sentences)
    train_ngrams = list(ngrams(train_sentences, n))
    voc_set = Counter(train_sentences)
    lm = Language_Model(train_ngrams, n, voc_set)
    print('done')
    return lm

def ngram_test(filename, start_test, end_test, n):
    """
    Generates the test inputs.
    Output:
        Some ngrams with their last word as label and the other as feed data.
    """
    test_sentences, stars = get_review_data(filename, start_test, end_test)
    test_sentences = [sentence[5:] for sentence in test_sentences]
    test_sentences = sentence_concat(test_sentences)
    test_ngrams = list(ngrams(test_sentences, n))
    return test_ngrams

def get_prediction(lm, test_ngrams, topn=10):
    """
    Generates the predictions, given the language model and the test inputs.
    """
    print('begin predicting')
    test_true_words = []
    test_pred_words = []
    k = 0
    for ngram in test_ngrams:
        k += 1
        if k % 100 == 0:
            print(k)
        prev_words = ngram[:-1]
        pred_words = lm.predict(prev_words, topn)
        test_true_words.append(ngram[-1])
        test_pred_words.append(pred_words)
    print('end predicting')
    return test_true_words, test_pred_words


def get_accuracy(true_words, pred_words, topn=10):
    '''
    Generates the top-n accuracy given the ground truth and predictions.
    '''
    print('begin getting accuracy')
    correct = 0
    for i in range(len(true_words)):
        true_word = true_words[i]
        pred_word_list = pred_words[i]

        if true_word in pred_word_list[0:topn]:
            correct += 1
    return correct / len(true_words)

def get_esaved(true_words, pred_words, topn=1):
    '''
    This function evaluates the model by calculating the eSaved as defined in checkpoint2.
    It use a different implementation from the dict_filter, as here we don't have a word2vec model.
    Inputs:
        model: the word2vec model precalculated
        true_words: the true words in the original text
        pred_words: the word vecs produced by the model
        topn: the number of nearest neighbours to be evaluated as correct, default to 1
        cons: the number of nearest neighbours to be considered, default to 20
    Output:
    The average eSaved.
    '''
    print('begin getting eSaved')
    
    # calculate the esaved
    eSaved = 0
    for i in range(len(true_words)):

        true_word = true_words[i]
        pred_words_list = pred_words[i]

        # build a trie tree to speed up the finding process
        t = trie.CharTrie()
        rt = {}
        for i in range(len(pred_words_list)):
            word = pred_words_list[i]
            t[word] = i
            rt[i] = word
        inputs = ''
        flag = False
        for i in range(len(true_word)):
            inputs += true_word[i]
            es = 1 - (i + 1) / (len(true_word) + 1)
            try:
                m = list(t[inputs:])
                m.sort()
                for j in range(min(topn, len(m))):
                    if rt[m[j]] == true_word:
                        eSaved += es
                        flag = True
                        break
            except KeyError:
                break
            if flag:
                break
    return eSaved / len(true_words)

def main():
    sys_params = system_params()
    model_params = model1_params()

    save_path = model_params.save_path
    save_folder = os.path.dirname(save_path)
    while os.path.isdir(save_folder):
        overwrite = input("There is a existing model on this path, overwrite? [y/n]")
        if (overwrite == 'y'):
            shutil.rmtree(save_folder)

    start_train, end_train = model_params.train_start, model_params.train_end
    start_test, end_test = model_params.test_start, model_params.test_end
    
    print('---------------- Getting Data and Training----------------')
    lm = ngram_train(sys_params.all_reviews_jsonfn, start_train, end_train, model_params.n)
    test_ngrams = ngram_test(sys_params.all_reviews_jsonfn, start_test, end_test, model_params.n)
    print('---------------- Done Getting Data and Training----------------')

    # begin predicting
    print("---------------- Predicting ----------------")
    test_true_words, test_pred_words = get_prediction(lm, test_ngrams, model_params.topn)
    print("---------------- Done Predicting ----------------")
    print("---------------- Getting Accuracy ----------------")
    acc = get_accuracy(test_true_words, test_pred_words, 10)
    print('Accuracy is {} for n = {}'.format(acc, model_params.n))
    print("---------------- Getting eSaved ----------------")
    eSaved = get_esaved(test_true_words, test_pred_words)
    print('eSaved is {} for n = {}'.format(eSaved, model_params.n))

if __name__ == '__main__':
    main()

