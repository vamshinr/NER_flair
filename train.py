from __future__ import print_function
import os
import sys
import traceback
import glob
import numpy as np
import time
import json

import torch
torch.cuda.empty_cache()

from pathlib import Path
from flair.data import Corpus
from flair.datasets import ColumnCorpus
from flair.embeddings import TokenEmbeddings, WordEmbeddings, StackedEmbeddings,CharacterEmbeddings,FlairEmbeddings, \
BytePairEmbeddings,BertEmbeddings,ELMoEmbeddings
from typing import List
# 5. initialize sequence tagger
from flair.models import SequenceTagger
from flair.embeddings import TransformerXLEmbeddings

# 6. initialize trainer
from flair.trainers import ModelTrainer

# # 8. plot training curves (optional)
# from flair.visual.training_curves import Plotter

from torch.optim.adam import Adam

from hyperopt import hp
from flair.hyperparameter.param_selection import SearchSpace, Parameter
from flair.hyperparameter.param_selection import SequenceTaggerParamSelector, OptimizationValue


container_prefix = '/opt/ml/'

input_path = container_prefix + 'input/data'
output_path = os.path.join(container_prefix, 'output')
checkpoint_path=os.path.join(container_prefix, 'output/checkpoint')
model_path = os.path.join(container_prefix, 'model')
param_path = os.path.join(container_prefix, 'input/config/hyperparameters.json')
albert_path = os.path.join(container_prefix, 'albert-base-v2')

# This algorithm has a single channel of input data called 'training'. Since we run in
# File mode, the input files are copied to the directory specified here.
channel_name = 'training'
training_path = os.path.join(input_path, channel_name)

#batch_size = 32
# num_classes = 10
#epochs = 100

def read_hyperparameters():
    global batch_size
    global epochs
    global learning_rate
    print("Reading hyperparameters")
    with open(param_path, 'r') as tc:
        hyperparameters = json.load(tc)
    if "batch_size" in hyperparameters:
        batch_size = int(hyperparameters["batch_size"])
    if "epochs" in hyperparameters:
        epochs = int(hyperparameters["epochs"])
    if "learning_rate" in hyperparameters:
        learning_rate = float(hyperparameters["learning_rate"])





# this is the folder in which train, test and dev files reside
data_folder = training_path



def train_model( ):
    #global corpus
    # define columns
    columns = {0: "text", 1: "ner"}
    #columns = {0: "text", 1: "pos", 2: "ner"}
    #columns = {0: "text", 1: "pos", 2: "np", 3: "ner"}
    data_folder = training_path
    print("data folder path",data_folder)
    # init a corpus using column format, data folder and the names of the train, dev and test files
    corpus: Corpus = ColumnCorpus(data_folder, columns,
                              train_file='train.txt',
                              dev_file='dev.txt',
                              test_file='test.txt')
                              
    max_tokens = 250
    corpus._train = [x for x in corpus.train if len(x) < max_tokens]
    corpus._dev = [x for x in corpus.dev if len(x) < max_tokens]
    corpus._test = [x for x in corpus.test if len(x) < max_tokens]

    print("Finished data standardization.........")


    # # 1. get the corpus
    # corpus: Corpus = WIKINER_ENGLISH().downsample(0.1)
    # print(corpus)

    # 2. what tag do we want to predict?
    tag_type = 'ner'

    # 3. make the tag dictionary from the corpus
    tag_dictionary = corpus.make_tag_dictionary(tag_type=tag_type)
    print(tag_dictionary.idx2item)
    #print("path is",f'{data_folder}/albert-base-v2')
    # 4. initialize embeddings
    embedding_types: List[TokenEmbeddings] = [

        # WordEmbeddings('/home/Balaram_bhukya/PycharmProjects/Flair_NER/nerData/wordembeddings/FT.50D.gensim'),
        #WordEmbeddings('glove'),

        # comment in this line to use character embeddings
        #CharacterEmbeddings(),
        BytePairEmbeddings('en'),
        #TransformerXLEmbeddings(),
        # comment in these lines to use flair embeddings
        FlairEmbeddings('news-forward'),
        #FlairEmbeddings('news-forward-fast',pooling='min')
        FlairEmbeddings('news-backward')
        #ELMoEmbeddings()
        #BertEmbeddings(bert_model_or_path=f'{data_folder}/albert-base-v2')
    ]
    embeddings: StackedEmbeddings = StackedEmbeddings(embeddings=embedding_types)



    tagger: SequenceTagger = SequenceTagger(hidden_size=256,
                                            embeddings=embeddings,
                                            tag_dictionary=tag_dictionary,
                                            tag_type=tag_type,
                                            use_crf=True)



    trainer: ModelTrainer = ModelTrainer(tagger, corpus)

    return trainer,corpus


def hyper_opt(corpus):
    print("hyper_opt is started")
    # define your search space
    search_space = SearchSpace()

    search_space.add(Parameter.EMBEDDINGS, hp.choice, options=[
        StackedEmbeddings([WordEmbeddings('en') ,
                           WordEmbeddings('glove'),
                           CharacterEmbeddings(),
                           FlairEmbeddings('news-forward'), FlairEmbeddings('news-backward'),ELMoEmbeddings()])
    ])

    search_space.add(Parameter.HIDDEN_SIZE, hp.choice, options=[256])
    #search_space.add(Parameter.RNN_LAYERS, hp.choice, options=[1, 2])
    #search_space.add(Parameter.DROPOUT, hp.uniform, low=0.0, high=0.5)
    search_space.add(Parameter.LEARNING_RATE, hp.choice, options=[0.01, 0.1])
    search_space.add(Parameter.MINI_BATCH_SIZE, hp.choice, options=[32,64])

    # create the parameter selector
    param_selector = SequenceTaggerParamSelector(
        corpus, 
        'ner', 
        #'/content/gdrive/My Drive/resume_ner_data/hyperparam_selection', 
        model_path,
        max_epochs=50, 
        training_runs=2,
        optimization_value=OptimizationValue.DEV_SCORE      
    )

    # start the optimization
    param_selector.optimize(search_space, max_evals=100)



def train():
    try:
        read_hyperparameters()
        trainer,corpus=train_model()
        print("hyper paramters are-----------",learning_rate,batch_size,epochs)
        # 7. start training
        '''
        trainer.train(model_path,
              learning_rate=learning_rate,
              mini_batch_size=batch_size,
              embeddings_storage_mode='gpu',
              train_with_dev=False,
              max_epochs=epochs,
              checkpoint=True
              )
        '''
        #checkpoint = checkpoint_path+'/checkpoint.pt'
        #checkpoint='/opt/ml/checkpoints/checkpoint.pt'
        #print(checkpoint)
        #print(os.path.getsize(checkpoint))
        #print(os.path.isfile(checkpoint))
        #print(os.listdir('/opt/ml'))
        #print(os.listdir('/opt/ml/model'))
        #print(os.listdir('/opt/ml/output'))
        #print(os.listdir('/opt/ml/checkpoints'))
        #print(os.path.getsize('/opt/ml/checkpoints/checkpoint.pt'))
        #trainer = ModelTrainer.load_checkpoint(checkpoint, corpus)
        trainer.train(model_path,
                      learning_rate=learning_rate,
                      mini_batch_size=batch_size,
                      max_epochs=epochs,
                      checkpoint=True)
        #hyper_opt(corpus)
              
        
    except Exception as e:
        # Write out an error file. This will be returned as the failureReason in the
        # DescribeTrainingJob result.
        trc = traceback.format_exc()
        with open(os.path.join(output_path, 'failure'), 'w') as s:
            s.write('Exception during training: ' + str(e) + '\n' + trc)
        # Printing this causes the exception to be in the training job logs, as well.
        print('Exception during training: ' + str(e) + '\n' + trc)
        # A non-zero exit code causes the training job to be marked as Failed.
        sys.exit(255)
        print("Finished training the model.")


# plotter = Plotter()
# plotter.plot_training_curves('loss.tsv')
# plotter.plot_weights('weights.txt')
if __name__ == '__main__':
    start = time.time()
    print(glob.glob(training_path+"/*"))
    # print(device_lib.list_local_devices())
    print("Script Status - Starting")
    train()
    print("Script Status - Finished")
    print("Total time taken to train the model: ", time.time() - start)

    # A zero exit code causes the job to be marked a succeeded.
    sys.exit(0)
