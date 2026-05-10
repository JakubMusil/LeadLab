from decimal import Decimal, InvalidOperation
from typing import Any, Mapping


_MISSING = object()


class RecordConditionContextBuilder:
    """Build a stable context for evaluating record condition trees."""

    def build(self, record) -> dict:
        return {
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
            "extra_data": record.extra_data or {},
        }

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
        if tree is None:
            return True

        if isinstance(tree, list):
            return all(self.evaluate(node, context) for node in tree)

        if not isinstance(tree, dict):
            return False

        op = str(tree.get("op") or tree.get("logic") or tree.get("operator") or "").lower()
        node_type = str(tree.get("type") or "").lower()
        negated = bool(tree.get("negated"))
        result = False

        if op in {"and", "or"}:
            children = tree.get("conditions") or tree.get("children") or []
            if not isinstance(children, list):
                return False
            if not children:
                result = op == "and"
            else:
                results = [self.evaluate(child, context) for child in children]
                result = all(results) if op == "and" else any(results)
        elif op == "not":
            child = tree.get("condition")
            if child is None:
                children = tree.get("conditions") or tree.get("children") or []
                if not isinstance(children, list) or len(children) != 1:
                    return False
                child = children[0]
            result = not self.evaluate(child, context)
        elif node_type == "group":
            return False
        else:
            result = self._evaluate_leaf(tree, context)

        return not result if negated else result

    def _evaluate_leaf(self, node: Mapping[str, Any], context: Mapping[str, Any]) -> bool:
        field = node.get("field") or node.get("path")
        if not field:
            return False

        actual = self._get_context_field(context, str(field))
        if actual is _MISSING:
            return False

        operator = str(node.get("operator", "eq")).lower()
        expected = node.get("value")

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
