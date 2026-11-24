from ipykernel.kernelapp import IPKernelApp

from .kernel import InetsKernel

IPKernelApp.launch_instance(kernel_class=InetsKernel)
