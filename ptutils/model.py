"""ptutils model.py.

Encapsulates a neural network model, criterion and optimizer.

"""
import random

import torch
import torch.nn as nn
import torch.optim as optim
from torch.autograd import Variable
from torch.nn.parallel import data_parallel

from ptutils.base import Base


class Model(Base):

    def __init__(self,
                 net=None,
                 criterion=None,
                 optimizer=None,
                 **kwargs):
        super(Model, self).__init__(**kwargs)

        self.net = net
        self.criterion = criterion
        self.optimizer = optimizer
        if self.optimizer.params is None:
            params = self.net.parameters()
        if hasattr(self.optimizer, 'defaults'):
            self.optimizer.optimizer = self.optimizer.optimizer_class(params,
                                                   **self.optimizer.defaults)
        else:
            self.optimizer.optimizer = self.optimizer.optimizer_class(params)
        self._loss = None
        if self.use_cuda:
            self.net.cuda(self.devices)

#    @property
#    def optimizer(self):
#        return self._optimizer
#
#    @optimizer.setter
#    def optimizer(self, value):
#        self._optimizer = value
#        if self._optimizer.params == None:
#            params = self.net.parameters()
#        if hasattr(self._optimizer, 'defaults'):
#            self._optimizer.optimizer = self._optimizer.optimizer_class(params,
#                                                   **self._optimizer.defaults)
#        else:
#            self._optimizer.optimizer = self._optimizer.optimizer_class(params)
#

    def forward(self, input):
        input_var = Variable(input)
        input_var = input_var.cuda(self.devices) if self.use_cuda else input_var
        return self.net(input_var)

    def loss(self, output, target):
        target_var = Variable(target)
        target_var = target_var.cuda(self.devices) if self.use_cuda else target_var
        loss = self.criterion(output, target_var)
        return loss

    def compute_gradients(self, loss=None):
        loss.backward()

    def apply_gradients(self):
        self.optimizer.step()

    def eval(self):
        """Set up model for evaluation."""
        self.net.eval()

    def train(self):
        """Set up model for training."""
        self.net.train()

    def optimize(self, loss=None):
        self.compute_gradients(loss=loss)
        self.apply_gradients()
        self.optimizer.zero_grad()

    def step(self, inputs):
        input, target = inputs
        output = self.forward(input)
        self._loss = self.loss(output, target)
        self.optimize(self._loss)
        return {'loss': self._loss}


class MNISTModel(Model):

    def __init__(self, *args, **kwargs):
        super(MNISTModel, self).__init__(*args, **kwargs)
        self.net = MNIST()
        self.learning_rate = 1e-3
        self.criterion = nn.CrossEntropyLoss()
        self.optimizer = optim.Adam(self.net.parameters(), self.learning_rate)


class MNIST(nn.Module, Base):

    def __init__(self):
        super(MNIST, self).__init__()

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

        self.cuda(self.devices)

    def forward(self, x):
        out = self.layer1(x)
        out = self.layer2(out)
        out = out.view(out.size(0), -1)
        out = self.fc(out)
        return out


class ConvMNIST(nn.Module, Base):
    def __init__(self):
        super(ConvMNIST, self).__init__()

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

    def forward(self, x):
        out = self.layer1(x)
        out = self.layer2(out)
        out = out.view(out.size(0), -1)
        return out


class FcMNIST(nn.Module, Base):

    def __init__(self):
        super(FcMNIST, self).__init__()
        self.fc = nn.Linear(7 * 7 * 32, 10)

    def forward(self, x):
        return self.fc(x)


class DynamicNet(nn.Module):
    def __init__(self, D_in, H, D_out):
        super(DynamicNet, self).__init__()
        self.input_linear = torch.nn.Linear(D_in, H)
        self.middle_linear = torch.nn.Linear(H, H)
        self.output_linear = torch.nn.Linear(H, D_out)

    def forward(self, x):
        h_relu = self.input_linear(x).clamp(min=0)
        for _ in range(random.randint(0, 3)):
            h_relu = self.middle_linear(h_relu).clamp(min=0)
        y_pred = self.output_linear(h_relu)
        return y_pred


class AlexNet(nn.Module):

    def __init__(self, num_classes=10):
        super(AlexNet, self).__init__()
        self.num_classes = num_classes

        self.features = nn.Sequential(
            nn.Conv2d(3, 64, kernel_size=11, stride=4, padding=2),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=3, stride=2),
            nn.Conv2d(64, 192, kernel_size=5, padding=2),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=3, stride=2),
            nn.Conv2d(192, 384, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(384, 256, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(256, 256, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=3, stride=2),
        )
        self.classifier = nn.Sequential(
            nn.Dropout(),
            nn.Linear(256 * 6 * 6, 4096),
            nn.ReLU(inplace=True),
            nn.Dropout(),
            nn.Linear(4096, 4096),
            nn.ReLU(inplace=True),
            nn.Linear(4096, self.num_classes),
        )

    def forward(self, x):
        x = self.features(x)
        x = x.view(x.size(0), 256 * 6 * 6)
        x = self.classifier(x)
        return x


class CIFARConv(nn.Module):

    def __init__(self, num_classes=10):
        super(CIFARConv, self).__init__()
        self.num_classes = num_classes

        self.features = nn.Sequential(
            nn.Conv2d(3, 64, kernel_size=5, padding=2),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(64, 192, kernel_size=5, padding=2),
            nn.BatchNorm2d(192),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(192, 384, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(384, 256, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(256, 256, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
        )
        self.classifier = nn.Sequential(
            nn.Dropout(),
            nn.Linear(256 * 4 * 4, 4096),
            nn.ReLU(inplace=True),
            nn.Dropout(),
            nn.Linear(4096, 4096),
            nn.ReLU(inplace=True),
            nn.Linear(4096, num_classes),
        )

    def reset_classifier(self, num_classes=10):
        self.classifier[6] = nn.Linear(4096, num_classes)

    def forward(self, x):
        x = self.features(x)
        x = x.view(x.size(0), 256 * 4 * 4)
        x = self.classifier(x)
        return x


class CIFARConvOld(nn.Module):
    def __init__(self, num_classes=10):
        super(CIFARConv, self).__init__()
        self.layer1 = nn.Sequential(
            nn.Conv2d(3, 16, kernel_size=5, padding=2),
            nn.BatchNorm2d(16),
            nn.ReLU(),
            nn.MaxPool2d(2))
        self.layer2 = nn.Sequential(
            nn.Conv2d(16, 20, kernel_size=5, padding=2),
            nn.BatchNorm2d(20),
            nn.ReLU(),
            nn.MaxPool2d(2))
        self.layer3 = nn.Sequential(
            nn.Conv2d(20, 20, kernel_size=5, padding=2),
            nn.BatchNorm2d(20),
            nn.ReLU(),
            nn.MaxPool2d(2))
        self.fc = nn.Linear(4 * 4 * 20, num_classes)

    def forward(self, x):
        out = self.layer1(x)
        out = self.layer2(out)
        out = self.layer3(out)
        out = out.view(out.size(0), -1)
        out = self.fc(out)
        return out

    def re_init_fc(self, num_classes=10):
        self.fc = nn.Linear(4 * 4 * 20, num_classes)
