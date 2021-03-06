"""ptutils tests.

These tests are meant to reflect the tests in the tfutils repository, e.g.
test_training(), test_training_save(), and test_validation().

These are higher level test than the test in test.py, but they will be integrated
into the same testing suite once they are finish.

Note about MongoDB:
The tests require a MongoDB instance to be available on the port defined by "testport" in
the code below.   This db can either be local to where you run these tests (and therefore
on 'localhost' by default) or it can be running somewhere else and then by ssh-tunneled on
the relevant port to the host where you run these tests.  [That is, before testing, you'd run
         ssh -f -N -L  [testport]:localhost:[testport] [username]@mongohost.xx.xx
on the machine where you're running these tests.   [mongohost] is the where the mongodb
instance is running.


"""

from __future__ import division, print_function, absolute_import

import sys
import time
import pymongo as pm
import re

import torch
import torch.nn as nn

sys.path.insert(0, '../')
import ptutils

LOG_LEVEL = 'WARNING'
MONGO_PORT = 27017
CUDA = 2


class MNIST(torch.nn.Module, ptutils.base.Base):
    def __init__(self, **kwargs):
        super(MNIST, self).__init__()
        ptutils.base.Base.__init__(self, **kwargs)

        self.layer1 = nn.Sequential(
            nn.Conv2d(1, 16, kernel_size=5, padding=2),
            nn.BatchNorm2d(16),
            nn.ReLU(),
            nn.MaxPool2d(2))
        self.layer2 = nn.Sequential(
            nn.Conv2d(16, 32, kernel_size=5, padding=2),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.MaxPool2d(2))
        self.fc = nn.Linear(7 * 7 * 32, 10)

    def forward(self, x):
        out = self.layer1(x)
        out = self.layer2(out)
        out = out.view(out.size(0), -1)
        out = self.fc(out)
        return out


class Criterion(nn.CrossEntropyLoss, ptutils.base.Base):

    def __init__(self, **kwargs):
        super(Criterion, self).__init__()
        # ptutils.base.Base.__init__(self, **kwargs)


def setup_params(exp_id=None):

    params = {
        'func': ptutils.runner.Runner,
        'name': 'MNISTRunner',
        'exp_id': exp_id,
        'description': 'The \'Hello, World!\' of deep learning',

        # Define Model Params
        'model': {
            'func': ptutils.model.Model,
            'name': 'MNIST',
            'use_cuda': True,
            'devices': CUDA,

            'net': {
                'func': MNIST,
                'name': 'mnist'},
            'criterion': {
                'func': Criterion,
                # 'func': nn.CrossEntropyLoss,
                # 'name': 'crossentropy',
                },
            'optimizer': {
                'func': ptutils.optimizer.Optimizer,
                'name': 'sgd_optimizer',
                'algorithm': 'SGD',
                'params': None,
                'defaults': {
                    'momentum': 0.9,
                    'lr': 0.05}}},

        # Define DataProvider Params
        'dataprovider': {
            'func': ptutils.data.MNISTProvider,
            'name': 'MNISTProvider',
            'n_threads': 4,
            'batch_size': 64,
            'modes': ('train', 'test')},

        # Define DBInterface Params
        'dbinterface': {
            'func': ptutils.database.MongoInterface,
            'name': 'mongo',
            'port': MONGO_PORT,
            'host': 'localhost',
            'database_name': 'ptutils_test',
            'collection_name': 'ptutils_test'},

        'train_params': {
            'num_steps': 50
        },

        'validation_params': {
        },

        'save_params': {
            'metric_freq': 25,
            'val_freq': 10},

        'load_params': {
            'restore': False,
            'dbinterface': {
                'func': ptutils.database.MongoInterface,
                'name': 'mongo',
                'port': MONGO_PORT,
                'host': 'localhost',
                'database_name': 'ptutils_test',
                'collection_name': 'ptutils_test'},
            'query': {'exp_id': exp_id},
            'restore_params': None,
            'restore_mapping': None
        }
    }
    return params


def test_training():
    """Illustrate training.

    This test illustrates how basic training is performed using the
    ptutils.runner.train_from_params function.  This is the first in a sequence of
    interconnected tests. It creates a pretrained model that is used by
    the next few tests (test_validation and test_feature_extraction).
    As can be seen by looking at how the test checks for correctness, after the
    training is run, results of training, including (intermittently) the full
    variables needed to re-initialize the tensorflow model, are stored in a
    MongoDB.

    """
    # Set up the parameters.
    exp_id = 'mnist_training'
    new_exp_id = 'new_mnist_training'
    params = setup_params(exp_id)

    # Clear database.
    conn = pm.MongoClient(host=params['dbinterface']['host'], port=params['dbinterface']['port'])
    conn[params['dbinterface']['database_name']][params['dbinterface']['collection_name']].delete_many({'exp_id': params['exp_id']})
    conn[params['dbinterface']['database_name']][params['dbinterface']['collection_name']].delete_many({'exp_id': new_exp_id})
    conn[params['dbinterface']['database_name']][params['dbinterface']['collection_name']].drop()
    assert conn[params['dbinterface']['database_name']][params['dbinterface']['collection_name']].find({'exp_id': params['exp_id']}).count() == 0
    assert conn[params['dbinterface']['database_name']][params['dbinterface']['collection_name']].find({'exp_id': new_exp_id}).count() == 0

    # Actually run the training.
    runner = ptutils.runner.Runner.init(params)
    runner.train()

    # Test if the number of saved documents is correct: (num_steps / metric_freq).
    assert runner.dbinterface.collection.find({'exp_id': params['exp_id']}).count() == (params['train_params']['num_steps'] // params['save_params']['metric_freq'])

    # Run another 50 steps of training on the same experiment id.
    params['train_params']['num_steps'] = 100
    params['load_params']['restore'] = True

    # Revive the experiment using little more than load_params.
    revive_params = {k: v for k, v in params.items() if k in ['func', 'exp_id', 'load_params', 'train_params']}

    runner = ptutils.runner.Runner.init(revive_params)
    runner.train()

    # Test if the number of saved documents is correct: (num_steps / metric_freq).
    assert runner.dbinterface.collection.find({'exp_id': params['exp_id']}).count() == (
        runner.train_params['num_steps'] // params['save_params']['metric_freq'])
    assert runner.dbinterface.collection.distinct('exp_id')[0] == params['exp_id']

    # Run 100 more steps but save to a new experiment id and on different GPU.
    params['exp_id'] = new_exp_id
    previous_num_steps = params['train_params']['num_steps']
    params['train_params']['num_steps'] = 200
    params['model']['devices'] = 1
    expected_num_records = (params['train_params']['num_steps'] - previous_num_steps) // params['save_params']['metric_freq']

    runner = ptutils.runner.Runner.init(params)
    runner.train()

    assert runner.dbinterface.collection.find({'exp_id': params['exp_id']}).count() == expected_num_records


def test_validation():
    """Illustrate validation.

    This is a test illustrating how to compute performance on a trained model on a new dataset,
    using the runner.test_from_params function.  This test assumes that test_training function
    has run first (to provide a pre-trained model to validate).
    After the test is run, results from the validation are stored in the MongoDB.
    (The test shows how the record can be loaded for inspection.)

    """
    # specify the parameters for the validation
    exp_id = 'mnist_validation'
    params = setup_params(exp_id)
    params['load_params']['restore'] = True
    params['load_params']['query'] = {'exp_id': 'mnist_training'}
    params['validation_params'] = {'num_steps': 10}

    # Clear database.
    conn = pm.MongoClient(
        host=params['dbinterface']['host'], port=params['dbinterface']['port'])
    conn[params['dbinterface']['database_name']][params['dbinterface']
                                                 ['collection_name']].delete_many({'exp_id': params['exp_id']})
    assert conn[params['dbinterface']['database_name']][params['dbinterface']
                                                        ['collection_name']].find({'exp_id': params['exp_id']}).count() == 0

    # actually run the model
    runner = ptutils.runner.Runner.init(params)
    runner.test()

    assert conn[params['dbinterface']['database_name']][params['dbinterface']
                                                        ['collection_name']].find({'exp_id': params['exp_id']}).count() == 1

    # Test validation during training
    params['exp_id'] = 'mnist_training'
    params['train_params']['num_steps'] = 200
    params['load_params']['restore'] = True

    # Revive the experiment using little more than load_params.
    revive_params = {k: v for k, v in params.items() if k in ['func', 'exp_id', 'load_params', 'train_params']}
    revive_params['validation_params'] = {'num_steps': 10}
    runner = ptutils.runner.Runner.init(revive_params)
    runner.train()


class DiffNameMNIST(torch.nn.Module, ptutils.base.Base):
    def __init__(self, **kwargs):
        super(DiffNameMNIST, self).__init__()
        ptutils.base.Base.__init__(self, **kwargs)

        self.new_layer1 = nn.Sequential(
            nn.Conv2d(1, 16, kernel_size=5, padding=2),
            nn.BatchNorm2d(16),
            nn.ReLU(),
            nn.MaxPool2d(2))
        self.new_layer2 = nn.Sequential(
            nn.Conv2d(16, 32, kernel_size=5, padding=2),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.MaxPool2d(2))
        self.new_fc = nn.Linear(7 * 7 * 32, 10)

    def forward(self, x):
        out = self.new_layer1(x)
        out = self.new_layer2(out)
        out = out.view(out.size(0), -1)
        out = self.new_fc(out)
        return out


class ThreeLayerMNIST(torch.nn.Module, ptutils.base.Base):
    def __init__(self, **kwargs):
        super(ThreeLayerMNIST, self).__init__()
        ptutils.base.Base.__init__(self, **kwargs)

        self.new_layer1 = nn.Sequential(
            nn.Conv2d(1, 16, kernel_size=5, padding=2),
            nn.BatchNorm2d(16),
            nn.ReLU(),
            nn.MaxPool2d(2))
        self.new_layer2 = nn.Sequential(
            nn.Conv2d(16, 32, kernel_size=5, padding=2),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.MaxPool2d(2))
        self.new_layer3 = nn.Sequential(
            nn.Conv2d(32, 32, kernel_size=5, padding=2),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.MaxPool2d(2))
        self.fc = nn.Linear(3 * 3 * 32, 10)

    def forward(self, x):
        out = self.new_layer1(x)
        out = self.new_layer2(out)
        out = self.new_layer3(out)
        out = out.view(out.size(0), -1)
        out = self.fc(out)
        return out


def test_remapping():
    """Illustrate remapping of layers.

    This test assumes that test_training function has run first.

    """
    exp_id = 'mnist_remapped_new_name'
    params = setup_params(exp_id)
    params['load_params']['restore'] = True
    params['train_params']['num_steps'] = 200

    params['load_params']['query'] = {'exp_id': 'mnist_training'}

    params['model']['net']['func'] = DiffNameMNIST
    params['load_params']['restore_mapping'] = {'model.net.' + key: 'model.net.' + re.sub('layer', 'new_layer', key) for key in MNIST().state_dict().keys()}

    params['load_params']['restore_mapping']['model.net.fc.weight'] = 'model.net.new_fc.weight'
    params['load_params']['restore_mapping']['model.net.fc.bias'] = 'model.net.new_fc.bias'

    runner = ptutils.runner.Runner.init(params)
    runner.train()

    exp_id = 'mnist_remapped_new_arch'
    params = setup_params(exp_id)
    params['load_params']['restore'] = True
    params['load_params']['query'] = {'exp_id': 'mnist_training'}

    params['model']['net']['func'] = ThreeLayerMNIST
    params['model']['net']['name'] = 'threelayermnist'
    params['load_params']['restore_mapping'] = {'model.net.' + key: 'model.net.' + re.sub('layer', 'new_layer', key) for key in MNIST().state_dict().keys() if 'layer' in key}
    params['load_params']['restore_params'] = re.compile(r'fc')

    runner = ptutils.runner.Runner.init(params)
    runner.train()


if __name__ == '__main__':
    test_training()
    test_validation()
    test_remapping()
