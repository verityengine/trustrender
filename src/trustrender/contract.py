"""Data-contract inference and validation for Jinja2 templates.

Infers a minimum structural contract from Jinja2 template usage and validates
caller data before rendering. Catches missing fields, null values, and
structural type mismatches (scalar vs object vs list) with path-based errors.

Include-aware: ``{% include %}`` directives are followed recursively.
Dynamic includes (``{% include some_var %}``) cannot be resolved statically
and mark the contract as partial.

Limitations:
- No int/str/float type narrowing — structural types only
  (scalar, object, list[object], list[scalar], unknown).
- ``required`` is a template-read heuristic, not business-semantic truth.
  A field is marked required=False only when ALL references occur inside
  a direct ``{% if field %}`` truthiness guard on that exact path.
- String method filtering is heuristic — unusual methods not in the filter
  list may appear as spurious child fields.
- No macro support.
- ``.j2.typ`` templates only — raw ``.typ`` gets no validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import jinja2
import jinja2.nodes as nodes

# -----------------------------------------------------------------------
# Data structures
# -----------------------------------------------------------------------

# Structural types. No int/str/float in v1.
SCALAR = "scalar"
OBJECT = "object"
LIST_OBJECT = "list[object]"
LIST_SCALAR = "list[scalar]"
UNKNOWN = "unknown"


@dataclass
class FieldSpec:
    """Describes one field in the inferred data contract."""

    path: str
    expected_type: str = SCALAR
    required: bool = True
    children: dict[str, FieldSpec] = field(default_factory=dict)


@dataclass
class ContractError:
    """One validation error with a path pointing into the caller's data."""

    path: str
    message: str
    expected: str
    actual: str


DataContract = dict[str, FieldSpec]


@dataclass
class InferenceResult:
    """Result of contract inference with metadata about completeness."""

    contract: DataContract
    is_partial: bool = False
    unresolved_includes: list[str] = field(default_factory=list)

# -----------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------

_JINJA_BUILTINS = frozenset(
    {
        "loop",
        "range",
        "lipsum",
        "true",
        "false",
        "none",
        "namespace",
        "cycler",
        "joiner",
    }
)

# Method names that should NOT become child fields when found at the
# tail of a Getattr chain inside a Call node.
_STRING_METHODS = frozenset(
    {
        "startswith",
        "endswith",
        "upper",
        "lower",
        "strip",
        "lstrip",
        "rstrip",
        "split",
        "rsplit",
        "replace",
        "find",
        "rfind",
        "index",
        "rindex",
        "count",
        "join",
        "format",
        "encode",
        "decode",
        "title",
        "capitalize",
        "swapcase",
        "center",
        "ljust",
        "rjust",
        "zfill",
        "isdigit",
        "isalpha",
        "isalnum",
        "isspace",
        "isupper",
        "islower",
    }
)


# -----------------------------------------------------------------------
# AST walking — infer_contract
# -----------------------------------------------------------------------


def infer_contract(template_path: Path) -> DataContract:
    """Parse a ``.j2.typ`` template and infer its minimum data contract.

    Returns a dict of top-level field names to FieldSpec trees describing
    the structural shape the template expects from caller data.

    Follows ``{% include %}`` directives recursively.  Dynamic includes
    that cannot be resolved statically are silently skipped (use
    ``infer_contract_with_metadata`` to see which includes were unresolved).
    """
    return infer_contract_with_metadata(template_path).contract


def infer_contract_with_metadata(template_path: Path) -> InferenceResult:
    """Like ``infer_contract`` but returns metadata about completeness.

    If the template uses dynamic includes (``{% include some_var %}``) or
    references missing fragments, ``is_partial`` is True and the
    unresolvable paths are listed in ``unresolved_includes``.
    """
    template_path = Path(template_path)
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(template_path.parent)),
        keep_trailing_newline=True,
    )
    source = env.loader.get_source(env, template_path.name)[0]

    try:
        ast = env.parse(source)
    except jinja2.TemplateSyntaxError:
        # Template has syntax errors — skip contract inference and let the
        # downstream template_preprocess stage handle and classify the error.
        return InferenceResult(contract={})

    walker = _ASTWalker(env=env)
    walker.walk(ast)
    return InferenceResult(
        contract=walker.contract,
        is_partial=bool(walker.unresolved_includes),
        unresolved_includes=list(walker.unresolved_includes),
    )


class _LoopInfo:
    """Tracks how a loop variable is used inside a for-body."""

    __slots__ = ("source_name", "element_attrs", "used_directly")

    def __init__(self, source_name: str) -> None:
        self.source_name = source_name
        self.element_attrs: list[list[str]] = []  # each entry is an attr chain
        self.used_directly = False

    def add_attr(self, attrs: list[str]) -> None:
        self.element_attrs.append(attrs)

    def mark_direct(self) -> None:
        self.used_directly = True


class _ASTWalker:
    """Recursive Jinja2 AST walker that builds a DataContract."""

    def __init__(self, env: jinja2.Environment | None = None) -> None:
        self.contract: DataContract = {}
        self._local_vars: set[str] = set()
        self._loop_info: dict[str, _LoopInfo] = {}
        # Set of field paths that have been seen inside a direct
        # truthiness guard ({% if field %}) and nowhere else.
        self._guarded_only: set[str] = set()
        # Set of field paths seen in an unconditional context.
        self._unconditional: set[str] = set()
        # Current direct-truthiness-guard variable (if any).
        self._guard_var: str | None = None
        # Include tracking.
        self._env = env
        self._visited_includes: set[str] = set()
        self.unresolved_includes: list[str] = []

    # -- public entry point -------------------------------------------

    def walk(self, node: nodes.Node) -> None:
        self._visit(node, guarded=False)

    # -- visitor dispatch ---------------------------------------------

    def _visit(self, node: nodes.Node, *, guarded: bool) -> None:
        method = f"_visit_{type(node).__name__}"
        visitor = getattr(self, method, None)
        if visitor is not None:
            visitor(node, guarded=guarded)
        else:
            self._visit_children(node, guarded=guarded)

    def _visit_children(self, node: nodes.Node, *, guarded: bool) -> None:
        for child in node.iter_child_nodes():
            self._visit(child, guarded=guarded)

    # -- node visitors ------------------------------------------------

    def _visit_Template(self, node: nodes.Template, *, guarded: bool) -> None:
        self._visit_children(node, guarded=guarded)

    def _visit_Output(self, node: nodes.Output, *, guarded: bool) -> None:
        self._visit_children(node, guarded=guarded)

    def _visit_Name(self, node: nodes.Name, *, guarded: bool) -> None:
        name = node.name
        if name in self._local_vars or name in _JINJA_BUILTINS:
            return
        if node.ctx == "store":
            return

        # Track whether this reference is guarded or unconditional.
        if guarded and self._guard_var == name:
            self._guarded_only.add(name)
        else:
            self._unconditional.add(name)

        # Check if this is a loop variable used directly (not via .attr).
        if name in self._loop_info:
            self._loop_info[name].mark_direct()
            return

        self._register_field(name, SCALAR, guarded=guarded)

    def _visit_Getattr(self, node: nodes.Getattr, *, guarded: bool) -> None:
        chain = _resolve_attr_chain(node)
        if not chain:
            self._visit_children(node, guarded=guarded)
            return

        root = chain[0]
        if root in _JINJA_BUILTINS:
            return

        attrs = chain[1:]
        # Filter string methods at the tail.
        if attrs and attrs[-1] in _STRING_METHODS:
            attrs = attrs[:-1]

        if root in self._loop_info:
            # Loop variable — record element attributes.
            if attrs:
                self._loop_info[root].add_attr(attrs)
            else:
                self._loop_info[root].mark_direct()
            return

        if root in self._local_vars:
            return

        if not attrs:
            # Track unconditional/guarded for root.
            if guarded and self._guard_var == root:
                self._guarded_only.add(root)
            else:
                self._unconditional.add(root)
            self._register_field(root, SCALAR, guarded=guarded)
        else:
            # Track unconditional/guarded for root.
            full_path = ".".join([root] + attrs)
            if guarded and self._guard_var == full_path:
                self._guarded_only.add(full_path)
            else:
                self._unconditional.add(root)
            self._register_nested(root, attrs, guarded=guarded)

    def _visit_For(self, node: nodes.For, *, guarded: bool) -> None:
        # Resolve the iterable — register as a list field.
        iter_name = _resolve_name(node.iter)
        target_name = _resolve_name(node.target)

        if iter_name and iter_name not in self._local_vars:
            if not guarded:
                self._unconditional.add(iter_name)
            self._register_field(iter_name, LIST_SCALAR, guarded=guarded)

        if target_name:
            self._local_vars.add(target_name)
            info = _LoopInfo(iter_name or "")
            self._loop_info[target_name] = info

        # Walk body.
        for child in node.body:
            self._visit(child, guarded=guarded)
        if node.else_:
            for child in node.else_:
                self._visit(child, guarded=guarded)

        # Collect element attributes and upgrade the list type.
        if target_name and iter_name:
            info = self._loop_info[target_name]
            if info.element_attrs:
                self._upgrade_list_to_object(iter_name, info.element_attrs)
            # If used directly AND has attrs, still list[object].
            # If used directly with no attrs, stays list[scalar].

        # Clean up scope.
        if target_name:
            self._local_vars.discard(target_name)
            self._loop_info.pop(target_name, None)

    def _visit_If(self, node: nodes.If, *, guarded: bool) -> None:
        # Determine if the test is a direct truthiness check on a single
        # variable path (the only case where we mark required=False).
        guard_path = _extract_direct_guard(node.test)
        is_direct_guard = guard_path is not None

        # Walk the test expression. For a direct truthiness guard like
        # {% if enclosures %}, the guard variable itself should be treated
        # as guarded (Jinja2 default Undefined is falsy, so the template
        # handles missing values gracefully). For non-guard tests like
        # {% if x != "foo" %}, the variable is unconditionally required.
        old_guard = self._guard_var
        if is_direct_guard:
            self._guard_var = guard_path
        self._visit(node.test, guarded=is_direct_guard or guarded)

        # Walk body with guard context.
        for child in node.body:
            self._visit(child, guarded=is_direct_guard or guarded)

        self._guard_var = old_guard

        # Walk elif branches.
        for elif_node in node.elif_:
            self._visit(elif_node, guarded=guarded)

        # Walk else branch.
        if node.else_:
            for child in node.else_:
                self._visit(child, guarded=guarded)

    def _visit_Assign(self, node: nodes.Assign, *, guarded: bool) -> None:
        # Walk value expression for data references.
        self._visit(node.node, guarded=guarded)
        # Add target to local vars (excluded from contract).
        target_name = _resolve_name(node.target)
        if target_name:
            self._local_vars.add(target_name)

    def _visit_Filter(self, node: nodes.Filter, *, guarded: bool) -> None:
        self._visit(node.node, guarded=guarded)
        for arg in node.args:
            self._visit(arg, guarded=guarded)
        for kwarg in node.kwargs:
            self._visit(kwarg, guarded=guarded)

    def _visit_Compare(self, node: nodes.Compare, *, guarded: bool) -> None:
        self._visit(node.expr, guarded=guarded)
        for op in node.ops:
            self._visit(op.expr, guarded=guarded)

    def _visit_Call(self, node: nodes.Call, *, guarded: bool) -> None:
        # Walk children for variable references, but the Call node itself
        # does not create fields (method calls are not data paths).
        self._visit(node.node, guarded=guarded)
        for arg in node.args:
            self._visit(arg, guarded=guarded)
        for kwarg in node.kwargs:
            self._visit(kwarg, guarded=guarded)

    def _visit_Concat(self, node: nodes.Concat, *, guarded: bool) -> None:
        self._visit_children(node, guarded=guarded)

    def _visit_CondExpr(self, node: nodes.CondExpr, *, guarded: bool) -> None:
        self._visit(node.test, guarded=guarded)
        self._visit(node.expr1, guarded=guarded)
        if node.expr2 is not None:
            self._visit(node.expr2, guarded=guarded)

    def _visit_Not(self, node: nodes.Not, *, guarded: bool) -> None:
        self._visit(node.node, guarded=guarded)

    def _visit_And(self, node: nodes.And, *, guarded: bool) -> None:
        self._visit(node.left, guarded=guarded)
        self._visit(node.right, guarded=guarded)

    def _visit_Or(self, node: nodes.Or, *, guarded: bool) -> None:
        self._visit(node.left, guarded=guarded)
        self._visit(node.right, guarded=guarded)

    def _visit_Include(self, node: nodes.Include, *, guarded: bool) -> None:
        # Only follow static includes (Const template names).
        if not isinstance(node.template, nodes.Const):
            # Dynamic include — can't resolve statically.
            self.unresolved_includes.append("<dynamic>")
            return

        include_name = node.template.value

        # Prevent circular includes.
        if include_name in self._visited_includes:
            return
        self._visited_includes.add(include_name)

        # Need an environment to resolve includes.
        if self._env is None:
            self.unresolved_includes.append(include_name)
            return

        # Load and parse the included template.
        try:
            source = self._env.loader.get_source(self._env, include_name)[0]
            inc_ast = self._env.parse(source)
        except (jinja2.TemplateNotFound, jinja2.TemplateSyntaxError):
            # Missing or broken fragment — graceful degradation.
            if not node.ignore_missing:
                self.unresolved_includes.append(include_name)
            return

        # Snapshot local scope before walking the include.
        # Always snapshot+restore to prevent fragments from leaking
        # local variable state back into the parent scope.
        saved_locals = self._local_vars.copy()
        saved_loop_info = dict(self._loop_info)
        saved_guard = self._guard_var

        if not node.with_context:
            # Without context: fragment has no access to parent locals.
            self._local_vars = set()
            self._loop_info = {}
            self._guard_var = None

        # Walk the fragment AST — its data references merge into our contract.
        self._visit(inc_ast, guarded=guarded)

        # Restore parent scope.
        self._local_vars = saved_locals
        self._loop_info = saved_loop_info
        self._guard_var = saved_guard

    def _visit_Const(self, node: nodes.Const, *, guarded: bool) -> None:
        pass  # Literal value, no data references.

    def _visit_MarkSafe(self, node: nodes.MarkSafe, *, guarded: bool) -> None:
        self._visit(node.expr, guarded=guarded)

    def _visit_MarkSafeIfAutoescape(
        self, node: nodes.MarkSafeIfAutoescape, *, guarded: bool
    ) -> None:
        self._visit(node.expr, guarded=guarded)

    # -- field registration -------------------------------------------

    def _register_field(self, name: str, expected_type: str, *, guarded: bool) -> None:
        """Register or update a top-level field."""
        if name in self.contract:
            spec = self.contract[name]
            spec.expected_type = _merge_type(spec.expected_type, expected_type)
            if not guarded:
                spec.required = True
        else:
            self.contract[name] = FieldSpec(
                path=name,
                expected_type=expected_type,
                required=not guarded,
            )

    def _register_nested(self, root: str, attrs: list[str], *, guarded: bool) -> None:
        """Register a nested field path like sender.name."""
        # Root is an object.
        if root in self.contract:
            spec = self.contract[root]
            spec.expected_type = _merge_type(spec.expected_type, OBJECT)
            if not guarded:
                spec.required = True
        else:
            spec = FieldSpec(path=root, expected_type=OBJECT, required=not guarded)
            self.contract[root] = spec

        # Walk nested attrs, creating children.
        current = spec
        for i, attr in enumerate(attrs):
            if attr not in current.children:
                child_path = root + "." + ".".join(attrs[: i + 1])
                current.children[attr] = FieldSpec(
                    path=child_path,
                    expected_type=SCALAR,
                    required=not guarded,
                )
            else:
                if not guarded:
                    current.children[attr].required = True
            if i < len(attrs) - 1:
                # Intermediate node must be an object.
                current.children[attr].expected_type = _merge_type(
                    current.children[attr].expected_type, OBJECT
                )
            current = current.children[attr]

    def _upgrade_list_to_object(self, list_name: str, element_attrs: list[list[str]]) -> None:
        """Upgrade a list field to list[object] with element children."""
        if list_name not in self.contract:
            return
        spec = self.contract[list_name]
        spec.expected_type = LIST_OBJECT

        for attr_chain in element_attrs:
            # Filter string methods from tail.
            chain = list(attr_chain)
            if chain and chain[-1] in _STRING_METHODS:
                chain = chain[:-1]
            if not chain:
                continue

            current = spec
            for i, attr in enumerate(chain):
                if attr not in current.children:
                    child_path = list_name + "[]." + ".".join(chain[: i + 1])
                    current.children[attr] = FieldSpec(
                        path=child_path,
                        expected_type=SCALAR,
                        required=True,
                    )
                if i < len(chain) - 1:
                    current.children[attr].expected_type = _merge_type(
                        current.children[attr].expected_type, OBJECT
                    )
                current = current.children[attr]


# -----------------------------------------------------------------------
# AST helpers
# -----------------------------------------------------------------------


def _resolve_attr_chain(node: nodes.Node) -> list[str]:
    """Resolve a chain of Getattr nodes to a list of names."""
    if isinstance(node, nodes.Getattr):
        parent = _resolve_attr_chain(node.node)
        if parent:
            return parent + [node.attr]
        return []
    if isinstance(node, nodes.Name):
        return [node.name]
    return []


def _resolve_name(node: nodes.Node) -> str | None:
    """Extract a simple name from a node (Name or Getattr chain root)."""
    if isinstance(node, nodes.Name):
        return node.name
    if isinstance(node, nodes.Getattr):
        chain = _resolve_attr_chain(node)
        return chain[0] if chain else None
    return None


def _extract_direct_guard(test: nodes.Node) -> str | None:
    """Return the field path if test is a direct truthiness check.

    Only returns a path for simple ``{% if field %}`` or
    ``{% if field.attr %}`` patterns — not comparisons, not compound
    expressions, not negations. This is deliberately conservative.
    """
    if isinstance(test, nodes.Name):
        if test.name not in _JINJA_BUILTINS:
            return test.name
    if isinstance(test, nodes.Getattr):
        chain = _resolve_attr_chain(test)
        if chain and chain[0] not in _JINJA_BUILTINS:
            return ".".join(chain)
    return None


def _merge_type(existing: str, new: str) -> str:
    """Merge two structural types. More specific type wins."""
    if existing == new:
        return existing
    # Object or list wins over scalar.
    if existing == SCALAR:
        return new
    if new == SCALAR:
        return existing
    # Unknown upgrades to anything.
    if existing == UNKNOWN:
        return new
    if new == UNKNOWN:
        return existing
    # list[scalar] upgrades to list[object].
    if {existing, new} == {LIST_SCALAR, LIST_OBJECT}:
        return LIST_OBJECT
    # Otherwise keep existing.
    return existing


# -----------------------------------------------------------------------
# Validation — validate_data
# -----------------------------------------------------------------------


def validate_data(contract: DataContract, data: dict) -> list[ContractError]:
    """Validate a data dict against an inferred contract.

    Returns a list of errors. Empty list means validation passed.
    Extra fields in data are allowed — the contract is a minimum spec.
    """
    errors: list[ContractError] = []
    _validate_level(contract, data, "", errors)
    return errors


def _validate_level(
    specs: dict[str, FieldSpec],
    data: dict,
    prefix: str,
    errors: list[ContractError],
) -> None:
    for name, spec in specs.items():
        path = f"{prefix}{name}" if not prefix else f"{prefix}.{name}"

        if name not in data:
            if spec.required:
                errors.append(
                    ContractError(
                        path=path,
                        message="missing required field",
                        expected=spec.expected_type,
                        actual="missing",
                    )
                )
            continue

        value = data[name]

        if value is None:
            if spec.required:
                errors.append(
                    ContractError(
                        path=path,
                        message=f"expected {spec.expected_type}, got null",
                        expected=spec.expected_type,
                        actual="null",
                    )
                )
            continue

        # Type checks.
        if spec.expected_type == OBJECT:
            if not isinstance(value, dict):
                errors.append(
                    ContractError(
                        path=path,
                        message=f"expected object, got {_type_name(value)}",
                        expected="object",
                        actual=_type_name(value),
                    )
                )
                continue
            if spec.children:
                _validate_level(spec.children, value, path, errors)

        elif spec.expected_type in (LIST_OBJECT, LIST_SCALAR):
            if not isinstance(value, list):
                errors.append(
                    ContractError(
                        path=path,
                        message=f"expected list, got {_type_name(value)}",
                        expected="list",
                        actual=_type_name(value),
                    )
                )
                continue
            if spec.expected_type == LIST_OBJECT and spec.children:
                for i, item in enumerate(value):
                    item_path = f"{path}[{i}]"
                    if not isinstance(item, dict):
                        errors.append(
                            ContractError(
                                path=item_path,
                                message=f"expected object, got {_type_name(item)}",
                                expected="object",
                                actual=_type_name(item),
                            )
                        )
                        continue
                    _validate_level(spec.children, item, item_path, errors)

        elif spec.expected_type == SCALAR:
            if isinstance(value, (dict, list)):
                errors.append(
                    ContractError(
                        path=path,
                        message=f"expected scalar, got {_type_name(value)}",
                        expected="scalar",
                        actual=_type_name(value),
                    )
                )

        # UNKNOWN type: existence check only, no type validation.


def _type_name(value: object) -> str:
    """Return a human-readable type name for error messages."""
    if value is None:
        return "null"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "list"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    return type(value).__name__


# -----------------------------------------------------------------------
# Error formatting
# -----------------------------------------------------------------------


def format_contract_errors(errors: list[ContractError], template_name: str) -> str:
    """One-line summary for TrustRenderError message."""
    n = len(errors)
    noun = "error" if n == 1 else "errors"
    return f"Data validation failed: {n} field {noun} in {template_name}"


def format_contract_detail(errors: list[ContractError], contract: DataContract) -> str:
    """Multi-line detail for TrustRenderError.detail."""
    lines: list[str] = []
    for err in errors:
        lines.append(f"  {err.path}: {err.message}")
    return "\n".join(lines)
