"""Typed failures with stable codes.

Each class also inherits the builtin exception that 0.1 raised (ValueError, KeyError, ...),
so existing callers that catch builtins keep working while new callers can branch on `code`.
"""
import json


class MemoryMergeError(Exception):
    code = 'internal'
    retryable = False
    exit_code = 1

    def __init__(self, message, hint=None, **details):
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.details = details

    def __str__(self):  # KeyError would otherwise repr() the message
        return self.message

    def to_dict(self):
        err = {'code': self.code, 'message': self.message, 'retryable': self.retryable}
        if self.hint: err['hint'] = self.hint
        if self.details: err['details'] = self.details
        return {'error': err}

    def to_json(self):
        return json.dumps(self.to_dict(), ensure_ascii=False)


class InvalidInput(MemoryMergeError, ValueError):
    code = 'invalid_input'; exit_code = 2

class LimitExceeded(InvalidInput):
    code = 'limit_exceeded'

class SensitiveContent(InvalidInput):
    """Content matched a credential pattern. Details carry pattern kinds, never the matched text."""
    code = 'sensitive_content'

class NotFound(MemoryMergeError, KeyError):
    code = 'not_found'; exit_code = 3

class Conflict(MemoryMergeError, ValueError):
    code = 'conflict'; exit_code = 4

class InvalidTransition(Conflict):
    code = 'invalid_transition'

class PermissionDenied(MemoryMergeError, PermissionError):
    code = 'permission_denied'; exit_code = 5

class ProviderError(MemoryMergeError, RuntimeError):
    code = 'provider_error'; retryable = True; exit_code = 6

class ProviderConfigError(ProviderError, ValueError):
    """Bad provider configuration; ValueError keeps 0.1's Provider(...) contract."""
    code = 'provider_config'; retryable = False

class ModelOutputInvalid(ProviderError, ValueError):
    """The model answered but the answer failed validation. Callers fail closed."""
    code = 'model_output_invalid'; retryable = False

class ModelDrift(ProviderError):
    """The model behind a configured name no longer reproduces its stored canary vectors."""
    code = 'model_drift'; retryable = False

class DependencyMissing(MemoryMergeError, ImportError):
    code = 'dependency_missing'; exit_code = 7

class SchemaError(MemoryMergeError, RuntimeError):
    code = 'schema_error'; exit_code = 8

class SchemaTooNew(SchemaError):
    code = 'schema_too_new'

class StorageBusy(MemoryMergeError, RuntimeError):
    code = 'storage_busy'; retryable = True; exit_code = 9
