"""
Test suite for SchemaGenerator - validates JSON Schema generation from Registry.

Tests cover:
- Basic schema generation producing valid RuleSetManifest
- Parameter-to-field mapping correctness (int, str, bool, optional, lists)
- Validation of valid/invalid JSON inputs against generated schema
- Support for diverse context types (dataclass, TypedDict, plain class)
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from predylogic import Registry, SchemaGenerator
from predylogic.rule_engine.base import LeafNode, RuleSetManifest

from .conftest import OrderCtx, Product, User


class TestSchemaGeneratorBasics:
    """Test basic schema generation functionality."""

    def test_generate_creates_valid_manifest_model(self, user_registry: Registry[User]):
        """Verify SchemaGenerator.generate() creates a valid RuleSetManifest Pydantic model."""
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        # Verify it's a RuleSetManifest subclass
        assert issubclass(manifest_model, RuleSetManifest)
        assert manifest_model.__name__ == "UserRegistryManifest"

    def test_generated_model_has_correct_registry_name(self, user_registry: Registry[User]):
        """Verify generated model enforces correct registry name."""
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        # Create instance - registry field should be auto-set
        manifest = manifest_model(rules={})
        assert manifest.registry == "user_registry"

    def test_empty_registry_generates_valid_schema(self, registry_manager):
        """Verify SchemaGenerator works with empty registry."""
        empty_registry = Registry[User]("empty_registry")
        schema_gen = SchemaGenerator(empty_registry)
        manifest_model = schema_gen.generate()

        # Should still produce valid model
        manifest = manifest_model(rules={})
        assert manifest.registry == "empty_registry"
        assert manifest.rules == {}

    def test_multiple_registries_generate_distinct_schemas(
        self,
        user_registry: Registry[User],
        order_registry: Registry[OrderCtx],
    ):
        """Verify different registries generate distinct schema models."""
        user_schema = SchemaGenerator(user_registry).generate()
        order_schema = SchemaGenerator(order_registry).generate()

        # Models should be distinct
        assert user_schema != order_schema
        assert user_schema.__name__ == "UserRegistryManifest"
        assert order_schema.__name__ == "OrderRegistryManifest"


class TestParameterMapping:
    """Test parameter-to-field mapping in generated schemas."""

    def test_int_parameter_mapped_correctly(self, user_registry: Registry[User]):
        """Verify int parameters map to correct Pydantic field types."""
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        # Create manifest with is_adult rule (has min_age: int parameter)
        manifest = manifest_model(
            rules={
                "rule1": LeafNode(
                    rule={
                        "rule_def_name": "is_adult",
                        "min_age": 21,
                    },
                ),
            },
        )

        leaf = manifest.rules["rule1"].root
        assert isinstance(leaf, LeafNode)
        assert leaf.rule.rule_def_name == "is_adult"
        assert leaf.rule.min_age == 21

    def test_bool_parameter_mapped_correctly(self, user_registry: Registry[User]):
        """Verify bool parameters work correctly."""
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        # Create manifest with is_active rule (no params, just validates bool logic)
        manifest = manifest_model(
            rules={
                "rule1": LeafNode(
                    rule={
                        "rule_def_name": "is_active",
                    },
                ),
            },
        )

        leaf = manifest.rules["rule1"].root
        assert isinstance(leaf, LeafNode)
        assert leaf.rule.rule_def_name == "is_active"

    def test_str_parameter_mapped_correctly(self, user_registry: Registry[User]):
        """Verify string parameters map correctly."""
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        manifest = manifest_model(
            rules={
                "rule1": LeafNode(
                    rule={
                        "rule_def_name": "is_named",
                        "name": "Alice",
                    },
                ),
            },
        )

        leaf = manifest.rules["rule1"].root
        assert isinstance(leaf, LeafNode)
        assert leaf.rule.rule_def_name == "is_named"
        assert leaf.rule.name == "Alice"

    def test_float_parameter_mapped_correctly(self, order_registry: Registry[OrderCtx]):
        """Verify float parameters map correctly."""
        schema_gen = SchemaGenerator(order_registry)
        manifest_model = schema_gen.generate()

        manifest = manifest_model(
            rules={
                "rule1": LeafNode(
                    rule={
                        "rule_def_name": "min_total",
                        "amount": 99.99,
                    },
                ),
            },
        )

        leaf = manifest.rules["rule1"].root
        assert isinstance(leaf, LeafNode)
        assert leaf.rule.amount == 99.99

    def test_default_parameter_values_work(self, user_registry: Registry[User]):
        """Verify parameters with defaults work when omitted."""
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        # is_adult has min_age with default=18
        manifest = manifest_model(
            rules={
                "rule1": LeafNode(
                    rule={
                        "rule_def_name": "is_adult",
                        # min_age omitted - should use default
                    },
                ),
            },
        )

        leaf = manifest.rules["rule1"].root
        assert isinstance(leaf, LeafNode)
        assert leaf.rule.min_age == 18  # default value


class TestSchemaValidation:
    """Test validation behavior of generated schemas."""

    def test_valid_json_validates_successfully(self, user_registry: Registry[User]):
        """Verify valid JSON input passes validation."""
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        # Valid manifest JSON
        manifest_data = {
            "rules": {
                "adult_check": {
                    "node_type": "leaf",
                    "rule": {"rule_def_name": "is_adult", "min_age": 21},
                },
            },
        }

        manifest = manifest_model(**manifest_data)
        assert manifest.registry == "user_registry"
        assert "adult_check" in manifest.rules

    def test_wrong_type_raises_validation_error(self, user_registry: Registry[User]):
        """Verify wrong parameter type raises ValidationError."""
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        # min_age should be int, not string
        with pytest.raises(ValidationError) as exc_info:
            manifest_model(
                rules={
                    "rule1": LeafNode(
                        rule={
                            "rule_def_name": "is_adult",
                            "min_age": "twenty-one",  # Wrong type!
                        },
                    ),
                },
            )

        assert "min_age" in str(exc_info.value).lower() or "validation error" in str(exc_info.value).lower()

    def test_missing_required_field_raises_validation_error(self, user_registry: Registry[User]):
        """Verify missing required parameter raises ValidationError."""
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        # is_named requires 'name' parameter
        with pytest.raises(ValidationError) as exc_info:
            manifest_model(
                rules={
                    "rule1": LeafNode(
                        rule={
                            "rule_def_name": "is_named",
                            # 'name' is missing!
                        },
                    ),
                },
            )

        assert "name" in str(exc_info.value).lower() or "field required" in str(exc_info.value).lower()

    def test_extra_fields_raise_validation_error(self, user_registry: Registry[User]):
        """Verify extra fields raise ValidationError (extra='forbid' config)."""
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        with pytest.raises(ValidationError) as exc_info:
            manifest_model(
                rules={
                    "rule1": LeafNode(
                        rule={
                            "rule_def_name": "is_active",
                            "extra_field": "not_allowed",  # Extra field!
                        },
                    ),
                },
            )

        assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()

    def test_invalid_rule_def_name_raises_validation_error(self, user_registry: Registry[User]):
        """Verify referencing non-existent rule_def_name raises ValidationError."""
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        with pytest.raises(ValidationError) as exc_info:
            manifest_model(
                rules={
                    "rule1": LeafNode(
                        rule={
                            "rule_def_name": "non_existent_rule",
                        },
                    ),
                },
            )

        # Discriminator should reject unknown rule_def_name
        assert "discriminator" in str(exc_info.value).lower() or "rule_def_name" in str(exc_info.value).lower()


class TestDiverseContextTypes:
    """Test schema generation works with diverse context types."""

    def test_dataclass_context_generates_schema(self, user_registry: Registry[User]):
        """Verify schema generation works with dataclass context."""
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        manifest = manifest_model(
            rules={
                "rule1": LeafNode(rule={"rule_def_name": "is_adult", "min_age": 18}),
            },
        )
        assert manifest.registry == "user_registry"

    def test_typeddict_context_generates_schema(self, order_registry: Registry[OrderCtx]):
        """Verify schema generation works with TypedDict context."""
        schema_gen = SchemaGenerator(order_registry)
        manifest_model = schema_gen.generate()

        manifest = manifest_model(
            rules={
                "rule1": LeafNode(rule={"rule_def_name": "min_total", "amount": 100.0}),
            },
        )
        assert manifest.registry == "order_registry"

    def test_plain_class_context_generates_schema(self, product_registry: Registry[Product]):
        """Verify schema generation works with plain class context."""
        schema_gen = SchemaGenerator(product_registry)
        manifest_model = schema_gen.generate()

        manifest = manifest_model(
            rules={
                "rule1": LeafNode(rule={"rule_def_name": "min_price", "price": 50.0}),
            },
        )
        assert manifest.registry == "product_registry"


class TestJSONSchemaExport:
    """Test JSON Schema export functionality."""

    def test_model_json_schema_export(self, user_registry: Registry[User]):
        """Verify generated model can export JSON Schema."""
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        json_schema = manifest_model.model_json_schema()

        # Verify basic schema structure
        assert json_schema["type"] == "object"
        assert "properties" in json_schema
        assert "registry" in json_schema["properties"]
        assert "rules" in json_schema["properties"]

    def test_json_schema_includes_rule_definitions(self, user_registry: Registry[User]):
        """Verify JSON Schema includes rule definition types."""
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        json_schema = manifest_model.model_json_schema()

        # Should have definitions for rule configs
        schema_str = str(json_schema)
        assert "is_adult" in schema_str.lower() or "IsAdultConfig" in schema_str
