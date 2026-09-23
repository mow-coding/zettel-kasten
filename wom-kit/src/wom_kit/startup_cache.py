"""Deterministic source-checked startup cache for two large installed modules.

Built only while materializing a verified runtime. The launcher verifies source
and payload hashes before executing retained bytes; ordinary launches write no
cache. The runtime's full wheel verifier also recompiles these two derived files
and compares their complete code metadata, so the cache manifest is not a new
trust root.
"""
from __future__ import annotations

import hashlib
import importlib.abc
import importlib.util
import io
import json
import marshal
from pathlib import Path
import struct
import sys
import types

MODULES = ("archive_services", "archive_cli")
MANIFEST = "startup-cache.json"
SCHEMA = "wom-kit/startup-cache/v1"
MAX_BYTES = 64 * 1024 * 1024
_COMPILED_PROOF_CACHE = set()


class StartupCacheError(ValueError):
    pass


def _read(path):
    info = path.lstat()
    if path.is_symlink() or getattr(info, "st_file_attributes", 0) & 1024 or not path.is_file() or info.st_size > MAX_BYTES:
        raise StartupCacheError("startup_cache_integrity_mismatch")
    raw = path.read_bytes()
    if len(raw) != info.st_size:
        raise StartupCacheError("startup_cache_integrity_mismatch")
    return raw


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _filename(name):
    return "__pycache__/" + name + "." + sys.implementation.cache_tag + ".pyc"


def compiled_bytes(raw, name):
    code = compile(raw, "wom_kit/" + name + ".py", "exec", dont_inherit=True, optimize=0)
    return importlib.util.MAGIC_NUMBER + struct.pack("<I", 3) + importlib.util.source_hash(raw) + marshal.dumps(code)


def _compiled_code_matches(payload, raw, name):
    # marshal may encode reference sharing differently for a large code object.
    # Check the decoded code and every byte consumed, not its incidental encoding.
    stream = io.BytesIO(payload[16:])
    retained = marshal.load(stream)
    if stream.tell() != len(payload) - 16 or not isinstance(retained, types.CodeType):
        return False
    expected = compile(raw, "wom_kit/" + name + ".py", "exec", dont_inherit=True, optimize=0)

    def same_code(left, right):
        # CodeType equality omits some debug metadata on older Python versions.
        # Every executable and provenance-bearing field must match the source.
        fields = ("co_argcount", "co_posonlyargcount", "co_kwonlyargcount",
            "co_nlocals", "co_stacksize", "co_flags", "co_code", "co_names",
            "co_varnames", "co_filename", "co_name", "co_qualname",
            "co_firstlineno", "co_linetable", "co_exceptiontable",
            "co_freevars", "co_cellvars")
        if sys.version_info < (3, 11) and left.co_lnotab != right.co_lnotab:
            return False
        if left != right or any(getattr(left, field, None) != getattr(right, field, None)
                                for field in fields):
            return False
        return all(
            same_code(a, b) if isinstance(a, types.CodeType) and isinstance(b, types.CodeType)
            else not isinstance(a, types.CodeType) and not isinstance(b, types.CodeType) and a == b
            for a, b in zip(left.co_consts, right.co_consts)
        ) and len(left.co_consts) == len(right.co_consts)

    return same_code(retained, expected)


def build(package_root):
    root = Path(package_root)
    directory = root / "__pycache__"
    directory.mkdir(exist_ok=True)
    if directory.is_symlink() or getattr(directory.lstat(), "st_file_attributes", 0) & 1024:
        raise StartupCacheError("startup_cache_integrity_mismatch")
    entries = {}
    for name in MODULES:
        source = _read(root / (name + ".py"))
        payload = compiled_bytes(source, name)
        destination = root / _filename(name)
        with destination.open("xb") as stream:
            stream.write(payload)
        entries[name] = {"source_sha256": _sha(source), "cache_sha256": _sha(payload),
            "source_size": len(source), "cache_size": len(payload)}
    document = {"schema": SCHEMA, "cache_tag": sys.implementation.cache_tag,
        "magic": importlib.util.MAGIC_NUMBER.hex(), "modules": entries}
    with (root / MANIFEST).open("xb") as stream:
        stream.write(json.dumps(document, sort_keys=True, separators=(",", ":")).encode("ascii"))
    return verify(root)


def verify(package_root, *, verify_compiled=False):
    root = Path(package_root)
    try:
        for directory in (root, root / "__pycache__"):
            if directory.is_symlink() or getattr(directory.lstat(), "st_file_attributes", 0) & 1024:
                raise ValueError()
        document = json.loads(_read(root / MANIFEST))
        if (set(document) != {"schema", "cache_tag", "magic", "modules"} or document["schema"] != SCHEMA
            or document["cache_tag"] != sys.implementation.cache_tag
            or document["magic"] != importlib.util.MAGIC_NUMBER.hex()
            or set(document["modules"]) != set(MODULES)):
            raise ValueError()
        retained = {}
        for name in MODULES:
            entry = document["modules"][name]
            source, payload = _read(root / (name + ".py")), _read(root / _filename(name))
            if (entry != {"source_sha256": _sha(source), "cache_sha256": _sha(payload), "source_size": len(source), "cache_size": len(payload)}
                or payload[:16] != importlib.util.MAGIC_NUMBER + struct.pack("<I", 3) + importlib.util.source_hash(source)):
                raise ValueError()
            if verify_compiled:
                proof_key = (sys.implementation.cache_tag, name, _sha(source), _sha(payload))
                if proof_key not in _COMPILED_PROOF_CACHE:
                    if not _compiled_code_matches(payload, source, name):
                        raise ValueError()
                    if len(_COMPILED_PROOF_CACHE) >= 8:
                        _COMPILED_PROOF_CACHE.clear()
                    _COMPILED_PROOF_CACHE.add(proof_key)
            retained["wom_kit." + name] = (str(root / (name + ".py")), payload)
        return retained
    except (OSError, ValueError, KeyError, TypeError, EOFError):
        raise StartupCacheError("startup_cache_integrity_mismatch") from None


class _RetainedLoader(importlib.abc.Loader):
    def __init__(self, path, payload):
        self.path, self.payload = path, payload
    def create_module(self, spec):
        return None
    def exec_module(self, module):
        module.__file__ = self.path
        # These exact bytes were verified; never reopen a mutable cache path.
        code = marshal.loads(self.payload[16:])
        exec(code, module.__dict__)


class _RetainedFinder(importlib.abc.MetaPathFinder):
    def __init__(self, modules):
        self.modules = modules
    def find_spec(self, fullname, path=None, target=None):
        if fullname not in self.modules:
            return None
        filename, payload = self.modules[fullname]
        return importlib.util.spec_from_loader(fullname, _RetainedLoader(filename, payload), origin=filename)


def activate():
    root = Path(__file__).parent
    if not (root / MANIFEST).exists():
        return None
    finder = _RetainedFinder(verify(root))
    sys.meta_path.insert(0, finder)
    return finder
