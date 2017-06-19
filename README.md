# PTUtils
PyTorch utilities for neural network research.

**Current status: pre-alpha. The API is still TDB and likely to change.**

## Overview

### Basic functionality
PTUtils will provide functionality for coordinating neural network experiments in PyTorch with varying degrees of control. PTUils will help users construct, run and monitor dynamic neural network models, retrieve data from multiple datasets 'on the fly', and provide an interface for interacting with common databases.

### Creating dynamic experiments
The 'define-by-run' paradigm established by deep learning frameworks such as Chainer, DyNet, PyTorch offers a powerful new way to structure neural network computations: the execution of the model/graph is conditioned on the state of the model itself, forming a *dynamic graph*. PTUtils attempts to *leverage and extend PyTorch's dynamic nature* by giving researchers a *dynamic experiment* whereby execution of the entire experiment is conditioned on the state of the experiment and any component contained within. The long-term motivation behind this approach is to provide researchers with a dynamic environment in which they can control the behavior/interactions of/between a model/collection of models as well as the data that is presented to the models, while saving the evolution of the environment behind the scenes. 

**Example use case:** Suppose you would like to study the interactions between two agents deployed in a common, simulated environment. Presumably, the behavior of each agent is determined by a separate model, and the data presented to each model is conditioned on the global environmental state. 

## Proposed Control Flow

The figure below depicts the intended high-level control flow of PTutils. Each module will operate independently as a standalone unit. You will be free to use any combination of modules that best suites your needs without worrying about inter-module dependencies. For example, you may choose to only use the DBInterface class for saving results to a database and handle the rest of the experiment yourself. Alternatively, you may choose to subclass `Config` and let PTUtils handle the rest. It's up to you!

![alt text](control_flow.png "Control Flow")

The details are explained below.

## Proposed design principles


At the core of PTUtils is the `Module`class, the base class for all ptutils objects that shamelessly attempts to generalize PyTorch's existing `torch.nn.Module`. A `Module` is an arbitrary, container-like object that fulfills three simple requirements:

1. All `Module` subclasses must either be **callable** or contain a callable attribute. In other words, all modules must perform an action.

2. All `Module` subclasses must implement a `state_dict()` (potential alias: `state()`) method that returns an object (likely a dict) that reflects the *state* of the module at the time `state_dict()` was called. What constitues a module's '*state*' can be completely specified by the user, although PTUtils offers concrete and sensible options.

3. All `Module` subclasses must implement a `load_state_dict()` (potential alias: `load_state()`) method that accepts the object returned by that module's `state_dict()` method and restores that module to the state it was in when `state_dict()` was called.


Enforcing this simple API attempts to address the notion that the environment in which a neural network operates should be free to evolve dynamically just as the network itself is. 

Although users are free to subclass the `Module` class in any way they please, ptutils provides a set of core modules with which users can conveniently carry out neural network experiments. The core putils modules (and their corresponding callables) include:

* `Module.call()`: Base class for all modules that raises a NotImplemented exception when called.
* `Session.run()`: Carry out a neural network experiement.
* `Model.forward()`: Execute the forward pass of a neural network model.
* `DataReader.read()`: Load data of a particular format.
* `DBInterface.access()`: Interact (read, write and query) with a database. 
* `DataLoader.__iter__()`: Iterate over data objects in a dataset.
* `Dataset.__getitem__()`: Return a single data object (image, label pair) from a dataset.
* `DataProvider.provide()`: Manage all datasets and generate specified `DataLoader`s.
* `Configuration.configure()`: Generate more complicated modules or groups of modules.

PTUtils will have one very special module: the `State` module. An instance `s` of the `State` class preserves the following:

```python
    s = s(*args, **kwargs) = s.state_dict(*args, **kwargs) = s.load_state_dict(*args, **kwargs).
```
Calling a state object or its two state_dict with any arguments will always return the original state object unmodified. Under the hood, the `State` class is an enhanced python dictionary with support for 'dot' notation and instrospective features such as recognizing any modules it contains.

With the exception of the `Module` base class, all PTUtils modules will come pre-fitted with default behavior that is '*compatible*' with the operation of the other modules. In other words, one can carry out a standard neural network experiment without writing any lines of code, provided that the modules are configured properly, of course. On the other hand, users can (and are encouraged) override any and/or all of the core module methods (within the boundaries of the API) and expect the other modules to remain functional. This flexibility is particularly useful for writing custom training loops while maintaining the same logging/saving behavior.
 optionally exhibits user-defined behavior. All that core components that make up a neural network experiment will subclass the :class:`Module` class. 

As a flexible container class, Modules can register and call other Modules as regular attributes, allowing users to nest them in a tree structure. The advantage here is that generating the state of a parent module is as simply as collecting the states of its children. Eventually, the states of modules without children will propogate back to the root module.

Many of the core ptutils modules specifically exploit this behavior. 
### `putils.session`

#### `class Session(object)`
At the core of PTUtils is the `Session` class (different from TF's `Session()`), the base class for all neural network experiments that specifically serves to *leverage and extend PyTorch's dynamic nature*. A `Session` object's purpose is to coordinate interactions between an evolving PTUtils `Model`, a `DBInterface` and a `DataProvider` throughout an experiment.

Sessions will have the ability to contain other Sessions as regular attributes, allowing users to nest them in a tree structure. This property gives users a method for managing a large number of related experiments all at once.



**Core Session API: TBD**

Candidate methods:

`Session.run()`
`Session.update()`

`Session.resume()`
`Session.restart()`

`Session._pause()`
`Session._stop()`

#### Initializing and Running a Session:

**Specify a Session configuration:** A primary method for generating a `Session` will be to pass its constructor a `ptutils.session.Config` (structure still TBD) object that users can subclass to specify how to construct the core `Session` objects and how they will interact. Ideally, passing a `Config` object to the `Session`'s constructor will automatically implement all the methods necessary to subclass a `Session`. The config object is equivalent to the `params` dictionary from TFUtils.

#### Coordinating Session dynamics:
This is where PTUtils will diverge from TFUtils most significantly and will require a great deal of planning and discussion.

**Option 1:** The hands-off approach would be to ask the user to explicitly specify the session's execution from beginning to end by leaving the `run()` method abstract. This would give all the control to the user but it would be the user's responsibility to make use of the conveniences provided by the Session class.

**Option 2:** Run a very generic training procedure and require the user to implement some sort of *state advancing function* (e.g.,  $Update:Session → Session$ that accepts a `Session` at step $t$ and returns the `Session` to be used at step $t + 1$) that will be called after every training step. In practice, this function wouldn't generate a new session at each training step. Rather, it would track  quantities of interest during a session's execution and trigger an event if some condition is met. Then, it would simply pause training, make modifications to a particular subset of components (e.g. change the `Model`'s criterion, switch its optimizer and retrieve a new `DataLoader`) and then resume the session.

**Tracking Session 'Status':**
Each `Session` ought to record basic properties about itself such as:
* whether a session is 'pending' vs. 'in-progress' vs. 'complete'
* For 'pending' sessions (ones that have made initial entries in the db but don't show any progress):
    * the error that is preventing progress.
    * its position in a queue (if there is one)
* For sessions 'in-progress':
    * execution stage (for sessions with discrete and sequential stages)
    * progress (% complete)
    * estimated time to completion
* For 'completed' sessions
    * overall outcome (success vs. failure)
* whether it is a new session or an attempt at restarting or re-running a previous session.

**Saving and restoring session state:**
The `Session` will then manage and make calls to one or multiple instances of a `DBInterface` (say you want to store data on both a server and client) and store data in a fashion specified in the `config`.

*Example `Session` use cases:*

**Coordinate multistage experiments:**
You would like to train your own alexnet on ImageNet and then finetune your model on a smaller, task-specific dataset as efficiently as possible and all in one go. You have access to ImageNet in HDF5 format, but you only have access to the raw jpegs of your smaller dataset (and cannot convert them to a different format). In your `config`, you could:

1. Specify an untrained alexnet as your `Model` with default training parameters, criterion and optimizer.
2. Connect the default `MongoInterface` to a running MongoDB instance.
3. Equip your `DataProvider` with two `Dataset` objects:
    * The default `ImageNet` dataset with an `HDF5Reader` (both provided with PTUtils)
    * A subclass of `torchvision.datasets.ImageFolder` in which you have specified the root directory path.
4. Deploy the Session with a multistage *state-advancing* function to track model error statistics. Its first stage will detect when training error drops significantly below validation error, pause training, request the ImageNet test set `Dataloader` from the `DataProvider` and begin the testing phase. If testing error is satisfactory, its second trigger will redeploy the trained model with a reinitialized bottleneck layer + classifier and request the `CustomDataset`'s training `DataLoader` to begin.

**Avoid exploding gradients**.

 You would like to train a model that notoriously suffers from *exploding gradients*. Assign a `Monitor` to track gradient magnitudes. If/when those gradients *explode*, its trigger will restore the model back to its most recent stable state and start employing the tips and tricks of your choice to keep those gradients in check.

 **Nested Sessions for efficient hyperparameter tuning**
 Specify a base configuration for a model you would like to tune. Deploy this config with a Session whose run method generates variations on the base config and deploys sub-sessions to run multiple training sessions in parallel. The top-level session monitors performance across all sub-sessions, retains only the best performing models and replacing poor performing models with new ones. 

### Additional (bonus) features

*  **Find available GPUs** In your config, specify the cluster details, start your session on node1 and `Session` will parse `sudo salt '*' cmd.run 'nvidia-smi'` (or an equivalent) to run your experiment on a node with available GPUs.

## Proposed API

### `putils.base`

#### `class Module(object)`

#### `class Config(object)`
Purpose: specify all details necessary to required to run an experiment.

**Structure: TBD**

---
### `ptutils.database`
Purpose: coordinate all events related to reading and writing to/from a specified database.

#### `class DBInterface(object)`

Interface for all database classes. Your database class should subclass this interface by maintaining the regular attribute `db_name` and implementing the following methods:

`save(obj)` Store the python object `obj` in the database `db` and return an identifier `object_id`.

`load(obj)` Return the python object `obj` from the database `db`.

`delete(obj)`
        Removes `obj` from the database.

#### `class MongoInterface(DBInterface)`

Simple and lightweight mongodb interface for saving experimental data files.

Usage:
```python
import torch
import numpy as np
from ptutils.database import MongoInterface

db = MongoInterface(db_name='db_name',
                    collection_name='collection_name',
                    hostname='hostname',
                    port='port')

# Nested dictionary containing numpy arrays and torch tensors:
doc = {'name': 'PyTorch experiment',
       'config': {'model': model_config,
                  'data': data_config},
       'results': [np.random.random((100, 100)),
                   torch.randn((100, 100))]}

# Save to database
doc_id = db.save(doc)

# Load from ID
doc_from_id = db.load_from_id(doc_id)

# Or load using a MongoDb query
doc_from_query = db.load({'name': 'PyTorch experiment'})

# Finally, delete from database
db.delete(doc_id)
```

---
### `ptutils.data`
#### `class DataProvider(object)`
Interface for all DataProvider subclasses.
The `DataProvider` class is responsible for parsing incoming requests from a `ptutils.Session` and returning the appropriate data.

To respond appropriately to requests, the `DataProvider` should manage a `Dataset` or collection of `Dataset`s (if a session needs to draw upon more than one data sources).

Critically, a `DataProvider` subclass must implement a `get_dataloader` method that accepts an arbitrary, user-defined 'request' for data and returns a valid `torch.utils.data.dataloader` object. This request can be conditioned on any aspect of the session's state (e.g. epoch, model accuracy, etc.).

A `torch.utils.data.dataloader` combines a `Dataset` and a `Sampler` to provide single- or multi-process iterators over the dataset. In constructing a `DataLoader`,
you are free to specify parameters such as batch size, data sampling strategies and the number of subprocesses to use for data loading.
See http://pytorch.org/docs/data.html for more details.

### `class Dataset(torch.utils.data.Dataset)`
Interface for all Dataset subclasses. This class simply extends Pytorch's Dataset class to be able to load data in different formats by introducing the notion of a `DataReader`. To be compatible with PyTorch's built-in DataLoader, each `DataSet` must implement the following:
```python
    def __getitem__(self, index):
        """Must return a data item given an index in [0, 1, ..., self.__len__()].

        Recommended implementation:

        1. Using `self.data_loader`, read data from `self.data_source` efficiently.
        2. Preprocess the data using `self.preprocessor`.
        3. Return a data item (e.g. image and label)
        """
        raise NotImplementedError()

    def __len__(self):
        """Return the total size (length) of you dataset."""
        raise NotImplementedError()
```

### `class DataReader(object)`

Interface for DataReader subclasses (e.g. HDF5, TFRecords, etc.). Reads data of a specified format efficiently. Must implement the
`read` method.

---
### `ptutils.support`

A module dedicated to providing compatibility with TFUtils.
## Proposed package structure
```
ptutils
| -- base.py
|    | *** CORE API GOES HERE ***
| -- data.py
|    | -- class DataProvider(object)              (abstract)
|    |    - get_dataloader()
|    | -- class Dataset(torch.utils.data.Dataset) (abstract)
|    |    - __getitem__(self, index)
|    |    - __len__(self)
|    | -- class DataReader(object)                (abstract)
|    |    - read(self)
|    | -- class ImageNet(DataSet)
|    | -- class HDF5Reader(DataReader)
| -- model.py
| -- utils.py
|    | -- logging
|    | -- metadata
|    | -- tensorboard
| -- session.py
|    | -- class Session(object)
|    |    - run()
|    |    - resume()
|    |    - restart()
|    |    - _pause()
|    |    - _stop()
|    | -- class Config(object)
|    | -- class Monitor(object)
| -- database.py
     | -- class DBInterface(object) (abstract)
     |    - save()
     |    - load()
     |    - delete()
     | -- MongoInterface(DBInterface)
     |    - save(document)
     |    - load(query)
     |    - del(object_id)
     |    - load_from_ids(ids)
```
