import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping


_MISSING = object()
logger = logging.getLogger(__name__)


class RecordConditionContextBuilder:
    """Build a stable context for evaluating record condition trees."""

    def build(
        self,
        record,
        *,
        changed_field: str | None = None,
        old_value: Any = None,
        new_value: Any = None,
        changed_field_source: str | None = None,
    ) -> dict:
        extra_data = record.extra_data if isinstance(record.extra_data, Mapping) else {}
        category_fields = extra_data.get("category_fields")
        if not isinstance(category_fields, Mapping):
            # Backward-compatible fallback for existing records where category fields
            # are persisted directly in extra_data root.
            category_fields = extra_data

        activities: list[dict[str, Any]] = []
        try:
            activity_qs = (
                record.activities
                .all()
                .only("type", "record_id", "customer_id", "proposal_id", "task_id", "created_at", "metadata")
            )
            activities = [
                {
                    "type": activity.type,
                    "entity_type": activity.entity_type,
                    "created_at": self._normalize(activity.created_at),
                    "tool_type": (
                        activity.metadata.get("tool_type")
                        if isinstance(activity.metadata, Mapping)
                        else None
                    ),
                }
                for activity in activity_qs
            ]
        except (AttributeError, TypeError, ValueError) as exc:
            logger.warning("Unable to load record activities for condition context: %s", exc)
            activities = []

        context = {
            "id": str(record.id),
            "firm_id": str(record.firm_id),
            "title": record.title or "",
            "status": record.status or "",
            "source": record.source or "",
            "value": self._normalize(record.value),
            "currency": record.currency or "",
            "score": self._normalize(getattr(record, "score", None)),
            "customer_id": str(record.customer_id) if record.customer_id else None,
            "assigned_to_id": str(record.assigned_to_id) if record.assigned_to_id else None,
            "company_id": str(record.company_id) if record.company_id else None,
            "contact_person_id": str(record.contact_person_id) if record.contact_person_id else None,
            "category_id": str(record.category_id) if record.category_id else None,
            "current_stage_id": str(record.current_stage_id) if record.current_stage_id else None,
            "parent_id": str(record.parent_id) if record.parent_id else None,
            "start_date": self._normalize(record.start_date),
            "end_date": self._normalize(record.end_date),
            "expires_at": self._normalize(record.expires_at),
            "notes": record.notes or "",
            "created_at": self._normalize(record.created_at),
            "updated_at": self._normalize(record.updated_at),
            "extra_data": extra_data,
            "category_fields": dict(category_fields),
            "activities": activities,
        }
        if changed_field is not None:
            context["change"] = {
                "field_key": changed_field,
                "source_type": changed_field_source,
                "old_value": self._normalize(old_value),
                "new_value": self._normalize(new_value),
            }
        return context

    def _normalize(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (Decimal, int, float, str, bool)):
            return value
        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
            except (TypeError, ValueError):
                return value
        return value


class ConditionTreeEvaluator:
    """Evaluate nested AND/OR/NOT condition trees against a context dict."""

    NUMERIC_OPERATORS = {"gt", "gte", "lt", "lte"}

    def evaluate(self, tree: Any, context: Mapping[str, Any]) -> bool:
        return self._evaluate_node(tree, context, set())

    def _evaluate_node(
        self,
        tree: Any,
        context: Mapping[str, Any],
        active_node_ids: set[int],
    ) -> bool:
        if tree is None:
            return True

        tree_id: int | None = None
        if isinstance(tree, (dict, list)):
            tree_id = id(tree)
            if tree_id in active_node_ids:
                return False
            active_node_ids.add(tree_id)

        if isinstance(tree, list):
            try:
                return all(self._evaluate_node(node, context, active_node_ids) for node in tree)
            finally:
                if tree_id is not None:
                    active_node_ids.discard(tree_id)

        if not isinstance(tree, dict):
            return False

        op = str(tree.get("op") or tree.get("logic") or tree.get("operator") or "").lower()
        node_type = str(tree.get("type") or "").lower()
        negated = bool(tree.get("negated"))
        result = False

        try:
            if node_type == "group" and not op:
                op = "and"

            if op in {"and", "or"}:
                children = tree.get("conditions") or tree.get("children") or []
                if not isinstance(children, list):
                    return False
                if not children:
                    # Fail-closed semantics:
                    # AND() is identity True, OR() is identity False.
                    result = op == "and"
                else:
                    results = [
                        self._evaluate_node(child, context, active_node_ids)
                        for child in children
                    ]
                    result = all(results) if op == "and" else any(results)
            elif op == "not":
                child = tree.get("condition")
                if child is None:
                    children = tree.get("conditions") or tree.get("children") or []
                    if not isinstance(children, list) or len(children) != 1:
                        return False
                    child = children[0]
                result = not self._evaluate_node(child, context, active_node_ids)
            else:
                result = self._evaluate_leaf(tree, context)
            return not result if negated else result
        finally:
            if tree_id is not None:
                active_node_ids.discard(tree_id)

    def _evaluate_leaf(self, node: Mapping[str, Any], context: Mapping[str, Any]) -> bool:
        source_type = str(node.get("source_type") or "").lower()
        # Keep legacy aliases for backward compatibility with older condition payloads.
        if source_type in {"field_change", "record_field_change"}:
            return self._evaluate_field_change_leaf(node, context)
        if source_type in {"category_field_change", "record_category_field_change"}:
            return self._evaluate_category_field_change_leaf(node, context)
        if source_type in {"category_field", "category_fields"}:
            return self._evaluate_category_field_leaf(node, context)
        if source_type in {"activity", "streamline_activity", "streamline_tool"}:
            return self._evaluate_activity_leaf(node, context, source_type)
        if source_type == "related_entity":
            return self._evaluate_related_entity_leaf(node, context)

        field = node.get("field") or node.get("path")
        if not field:
            return False

        actual = self._get_context_field(context, str(field))
        if actual is _MISSING:
            return False

        operator = str(node.get("operator", "eq")).lower()
        expected = node.get("value")
        return self._evaluate_operator(actual, operator, expected)

    def _evaluate_category_field_leaf(self, node: Mapping[str, Any], context: Mapping[str, Any]) -> bool:
        key = node.get("category_field_key") or node.get("field") or node.get("path")
        if not key:
            return False

        key = str(key)
        if key.startswith("category_fields."):
            key = key[len("category_fields."):]

        category_fields = context.get("category_fields")
        if not isinstance(category_fields, Mapping):
            return False
        if key not in category_fields:
            return False

        actual = category_fields[key]
        operator = str(node.get("operator", "eq")).lower()
        expected = node.get("value")
        return self._evaluate_operator(actual, operator, expected)

    def _evaluate_field_change_leaf(self, node: Mapping[str, Any], context: Mapping[str, Any]) -> bool:
        field = node.get("field") or node.get("path")
        if not field:
            return False

        change = self._resolve_change_context(context, str(field), source_type="field")
        if change is None:
            return False
        return self._evaluate_change_operator(node, change)

    def _evaluate_category_field_change_leaf(self, node: Mapping[str, Any], context: Mapping[str, Any]) -> bool:
        key = node.get("category_field_key") or node.get("field") or node.get("path")
        if not key:
            return False

        key = str(key)
        if key.startswith("category_fields."):
            key = key[len("category_fields."):]

        change = self._resolve_change_context(context, key, source_type="category_field")
        if change is None:
            return False
        return self._evaluate_change_operator(node, change)

    def _resolve_change_context(
        self,
        context: Mapping[str, Any],
        field_key: str,
        *,
        source_type: str,
    ) -> Mapping[str, Any] | None:
        field_changes = context.get("field_changes")
        if isinstance(field_changes, Mapping):
            field_change = field_changes.get(field_key)
            if isinstance(field_change, Mapping):
                return field_change

        change = context.get("change")
        if isinstance(change, Mapping):
            change_field_key = change.get("field_key")
            if change_field_key is not None and str(change_field_key) == field_key:
                change_source_type = self._normalize_change_source(change.get("source_type"))
                if change_source_type in {None, source_type}:
                    return change

        changed_field = context.get("changed_field")
        if changed_field is None or str(changed_field) != field_key:
            return None

        changed_source = self._normalize_change_source(context.get("changed_field_source"))
        if changed_source not in {None, source_type}:
            return None

        return {
            "old_value": context.get("old_value"),
            "new_value": context.get("new_value"),
        }

    def _normalize_change_source(self, source: Any) -> str | None:
        if source is None:
            return None
        source_value = str(source).lower()
        if source_value in {"field", "standard_field", "record_field"}:
            return "field"
        if source_value in {"category_field", "record_category_field"}:
            return "category_field"
        return source_value

    def _evaluate_change_operator(self, node: Mapping[str, Any], change: Mapping[str, Any]) -> bool:
        """Evaluate changed* operators.

        `value` is the canonical payload key; `from_value`/`to_value` stay supported
        for older clients that emitted explicit directional keys.
        """
        old_value = change.get("old_value")
        new_value = change.get("new_value")
        has_changed = not self._values_equal(old_value, new_value)

        operator = str(node.get("operator", "changed")).lower()
        expected = node.get("value")
        if operator == "changed":
            return has_changed
        if operator == "changed_from":
            expected_from = node.get("from_value", expected)
            return has_changed and self._values_equal(old_value, expected_from)
        if operator == "changed_to":
            expected_to = node.get("to_value", expected)
            return has_changed and self._values_equal(new_value, expected_to)
        return False

    def _evaluate_related_entity_leaf(self, node: Mapping[str, Any], context: Mapping[str, Any]) -> bool:
        entity_type = node.get("entity_type") or node.get("related_entity_type")
        if not entity_type:
            return False

        entity_type = str(entity_type).lower()
        field_map = {
            "customer": "customer_id",
            "company": "company_id",
            "contact_person": "contact_person_id",
            "assigned_to": "assigned_to_id",
            "category": "category_id",
            "current_stage": "current_stage_id",
            "stage": "current_stage_id",
            "parent": "parent_id",
        }
        field_key = field_map.get(entity_type)
        if field_key is None:
            return False

        has_entity = context.get(field_key) is not None
        operator = str(node.get("operator", "exists")).lower()
        expected = node.get("value")
        if operator == "exists":
            return has_entity
        if operator in {"not_exists", "missing"}:
            return not has_entity
        if operator == "eq":
            if isinstance(expected, bool):
                return has_entity is expected
            return has_entity
        if operator == "neq":
            if isinstance(expected, bool):
                return has_entity is not expected
            return not has_entity
        return False

    def _evaluate_activity_leaf(
        self,
        node: Mapping[str, Any],
        context: Mapping[str, Any],
        source_type: str,
    ) -> bool:
        activities = context.get("activities")
        if not isinstance(activities, list):
            return False

        expected_type, expected_tool_type, expected_entity_type = self._resolve_activity_filters(node, source_type)

        matched = 0
        for activity in activities:
            if not isinstance(activity, Mapping):
                continue
            if expected_type is not None and str(activity.get("type")) != str(expected_type):
                continue
            if expected_tool_type is not None:
                tool_value = activity.get("tool_type")
                if tool_value is None:
                    tool_value = activity.get("type")
                if str(tool_value) != str(expected_tool_type):
                    continue
            if expected_entity_type is not None and str(activity.get("entity_type")) != str(expected_entity_type):
                continue
            if not self._match_time_window(activity, node.get("time_window")):
                continue
            matched += 1

        operator = str(node.get("operator", "exists")).lower()
        expected = node.get("value")
        if operator == "exists":
            return matched > 0
        if operator in {"not_exists", "missing"}:
            return matched == 0
        if operator == "eq":
            if isinstance(expected, bool):
                return (matched > 0) is expected
            return matched > 0
        if operator == "neq":
            if isinstance(expected, bool):
                return (matched > 0) is not expected
            return matched == 0
        if operator in self.NUMERIC_OPERATORS:
            return self._evaluate_operator(matched, operator, expected)
        return False

    def _resolve_activity_filters(
        self,
        node: Mapping[str, Any],
        source_type: str,
    ) -> tuple[Any, Any, Any]:
        expected_type = node.get("activity_type")
        expected_tool_type = node.get("tool_type")
        expected_entity_type = node.get("entity_type")
        expected_value = node.get("value")

        if source_type == "streamline_tool" and not expected_tool_type and expected_value is not None:
            expected_tool_type = expected_value
        if source_type in {"activity", "streamline_activity"} and not expected_type and expected_value is not None:
            expected_type = expected_value

        return expected_type, expected_tool_type, expected_entity_type

    def _match_time_window(self, activity: Mapping[str, Any], time_window: Any) -> bool:
        if not time_window:
            return True
        if not isinstance(time_window, Mapping):
            return False

        created_at = self._parse_datetime(activity.get("created_at"))
        if created_at is None:
            return False

        hours = time_window.get("last_hours")
        days = time_window.get("last_days")
        delta: timedelta | None = None

        if hours is not None:
            hours_num = self._to_decimal(hours)
            if hours_num is None or hours_num < 0:
                return False
            delta = timedelta(hours=float(hours_num))
        elif days is not None:
            days_num = self._to_decimal(days)
            if days_num is None or days_num < 0:
                return False
            delta = timedelta(days=float(days_num))

        if delta is None:
            return False

        return created_at >= datetime.now(timezone.utc) - delta

    def _parse_datetime(self, value: Any) -> datetime | None:
        if isinstance(value, datetime):
            dt_value = value
        elif isinstance(value, str):
            raw = value.strip()
            if raw.endswith("Z"):
                raw = f"{raw[:-1]}+00:00"
            try:
                dt_value = datetime.fromisoformat(raw)
            except ValueError:
                return None
        else:
            return None

        if dt_value.tzinfo is None:
            return dt_value.replace(tzinfo=timezone.utc)
        return dt_value.astimezone(timezone.utc)

    def _evaluate_operator(self, actual: Any, operator: str, expected: Any) -> bool:
        if operator == "eq":
            return str(actual) == str(expected)
        if operator == "neq":
            return str(actual) != str(expected)
        if operator == "contains":
            return str(expected).lower() in str(actual).lower()

        if operator in self.NUMERIC_OPERATORS:
            actual_num = self._to_decimal(actual)
            expected_num = self._to_decimal(expected)
            if actual_num is None or expected_num is None:
                return False
            if operator == "gt":
                return actual_num > expected_num
            if operator == "gte":
                return actual_num >= expected_num
            if operator == "lt":
                return actual_num < expected_num
            if operator == "lte":
                return actual_num <= expected_num

        return False

    def _get_context_field(self, context: Mapping[str, Any], field: str) -> Any:
        current: Any = context
        for part in field.split("."):
            if isinstance(current, Mapping):
                if part not in current:
                    return _MISSING
                current = current[part]
                continue
            return _MISSING
        return current

    def _to_decimal(self, value: Any) -> Decimal | None:
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return None

    def _values_equal(self, left: Any, right: Any) -> bool:
        """Compare values with safe handling for None versus stringified values."""
        if left is None or right is None:
            return left is right
        return str(left) == str(right)


def evaluate_condition_rule_outputs(
    rules: list[Any],
    context: Mapping[str, Any],
    *,
    evaluator: ConditionTreeEvaluator | None = None,
) -> list[dict[str, Any]]:
    """Evaluate active rules and return their effect payloads in deterministic order."""
    if evaluator is None:
        evaluator = ConditionTreeEvaluator()

    outputs: list[dict[str, Any]] = []
    for rule in _sort_rules_for_evaluation(rules):
        if not _rule_is_active(rule):
            continue
        if not evaluator.evaluate(_rule_attr(rule, "condition_tree", {}), context):
            continue
        outputs.append(
            {
                "rule_id": _rule_attr(rule, "id"),
                "name": _rule_attr(rule, "name", ""),
                "priority": _to_int(_rule_attr(rule, "priority"), default=100),
                "effect": _rule_attr(rule, "effect"),
                "severity": _rule_attr(rule, "severity"),
                "effect_config": _rule_attr(rule, "effect_config", {}),
            }
        )
    return outputs


def _sort_rules_for_evaluation(rules: list[Any]) -> list[Any]:
    def _created_at_key(rule: Any) -> str:
        created_at = _rule_attr(rule, "created_at")
        if created_at is None:
            return ""
        if hasattr(created_at, "isoformat"):
            try:
                return created_at.isoformat()
            except (TypeError, ValueError):
                return str(created_at)
        return str(created_at)

    return sorted(
        list(rules),
        key=lambda rule: (
            _to_int(_rule_attr(rule, "priority"), default=100),
            _created_at_key(rule),
            str(_rule_attr(rule, "id", "")),
        ),
    )


def _rule_attr(rule: Any, key: str, default: Any = None) -> Any:
    if isinstance(rule, Mapping):
        return rule.get(key, default)
    return getattr(rule, key, default)


def _rule_is_active(rule: Any) -> bool:
    if isinstance(rule, Mapping):
        return bool(rule.get("is_active", True))
    return bool(getattr(rule, "is_active", True))


def _to_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
