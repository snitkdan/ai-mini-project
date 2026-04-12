from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Protocol

from braintrust import init_logger
from braintrust.integrations.langchain import BraintrustCallbackHandler


if TYPE_CHECKING:
    from langchain_core.callbacks import BaseCallbackHandler


class ObservabilityDeps(Protocol):
    @staticmethod
    def init() -> None: ...
    @staticmethod
    def make_callback_handler() -> BaseCallbackHandler | None: ...


@dataclass
class BraintrustDeps:
    @staticmethod
    def init() -> None:
        init_logger(
            project="ai-mini-project",
            api_key=os.environ.get("BRAINTRUST_API_KEY"),
        )

    @staticmethod
    def make_callback_handler() -> BaseCallbackHandler | None:
        return BraintrustCallbackHandler()


@dataclass
class NoopDeps:
    @staticmethod
    def init() -> None:
        pass

    @staticmethod
    def make_callback_handler() -> BaseCallbackHandler | None:
        return None


# Enforce subtypes conform to interface
_braintrust_check: ObservabilityDeps = BraintrustDeps()
_noop_check: ObservabilityDeps = NoopDeps()
