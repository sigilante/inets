"""The Jupyter side: hands each cell to a :class:`~inets_kernel.session.Session` and
sends back what it returns."""
from ipykernel.kernelbase import Kernel

from . import __version__
from .session import Session


class InetsKernel(Kernel):
    implementation = "inets"
    implementation_version = __version__
    language = "inets"
    language_version = "0.1"
    language_info = {"name": "inets", "file_extension": ".inet", "mimetype": "text/plain", "pygments_lexer": "text"}
    banner = "Interaction nets. Try: con (a b) = dup (era era)   or   %help"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cells = Session()

    async def do_execute(self, code, silent, store_history=True, user_expressions=None, allow_stdin=False,
                         *, cell_meta=None, cell_id=None):
        error = None
        try:
            outputs = self.cells.execute(code)
        except Exception as e:      # a fault of the kernel's own: say so, and keep going
            outputs, error = [], f"{type(e).__name__}: {e}"
        for o in outputs:
            if o.kind == "error":
                error = o.data
            elif not silent and o.kind == "svg":
                self.send_response(self.iopub_socket, "display_data",
                                   {"data": {"image/svg+xml": o.data, "text/plain": "(a picture of the net)"}, "metadata": {}})
            elif not silent:
                self.send_response(self.iopub_socket, "stream", {"name": "stdout", "text": o.data + "\n"})
        if error is not None:
            reply = {"ename": "Error", "evalue": error, "traceback": [error]}
            if not silent:
                self.send_response(self.iopub_socket, "error", reply)
            return {"status": "error", "execution_count": self.execution_count, **reply}
        return {"status": "ok", "execution_count": self.execution_count, "payload": [], "user_expressions": {}}

    def do_is_complete(self, code):
        return {"status": "complete"}
