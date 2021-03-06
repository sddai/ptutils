import torch
from ptutils.base import Base


class Optimizer(Base):
    def __init__(self, algorithm=None, params=None, defaults=None, **kwargs):
        """Initialize an optimizer for training.

        Args:
            algorithm (str or callable): Name of the optimizer when str, handle to the optimizer class when callable.
                If a name is provided, this optimizer looks for the optimizer in `torch.optim`
            params (dict or list of dict): Specifies the parameter group.
                Defaults to model.parameters() if None.
            **kwargs: Keyword Arguments.

        Raises:
            NotImplementedError: Description.

        """
        super(Optimizer, self).__init__(**kwargs)
        self.params = params
        self.defaults = defaults
        self.algorithm = algorithm
        if isinstance(self.algorithm, (str, unicode)):
            optimizer_class = getattr(torch.optim, self.algorithm, None)
            if optimizer_class is None:
                # Look for algorithm in extensions
                optimizer_class = getattr(optimizers, self.algorithm, None)
            assert optimizer_class is not None, "Optimizer {} not found.".format(
                self.algorithm)
        elif callable(self.algorithm):
            optimizer_class = self.algorithm
        else:
            raise NotImplementedError

        self.optimizer_class = optimizer_class
        self._exclude_from_params = ['optimizer']
        if getattr(self, 'params', None) is not None:
            optimizer_class.__init__(self, self.params, self.defaults)

    # def to_params(self):
    #     params = super(Optimizer, self).to_params()
    #     return {name: param for name, param in params.items()
    #             if name not in ['optimizer']}

    def step(self, closure=None):
        return self.optimizer.step(closure=closure)

    def zero_grad(self):
        return self.optimizer.zero_grad()

    def compute_gradients(self, loss):
        loss.backward()

    def apply_gradients(self):
        self.step()

    def optimize(self, loss):
        self.compute_gradients(loss)
        self.apply_gradients()

    def __repr__(self):
        return Base.__repr__(self)
