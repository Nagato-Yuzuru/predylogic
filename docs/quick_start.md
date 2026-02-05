# Quick Start Guide

Welcome to Predylogic! This guide will help you get up and running with the core features in just a few minutes.

## Installation

```bash
pip install predylogic
```

## Overview

Predylogic enables you to:

- **Define rules** that encapsulate business logic
- **Compose rules** using logical operators (AND, OR, NOT)
- **Generate JSON schemas** for rule configuration
- **Execute rules** dynamically with different contexts
- **Hot-reload rules** without restarting your application

## 1. Registering Rule Definitions

The first step is to create a **Registry** and register your rule definitions. A registry is a collection of rule
definitions for a specific context type.

### Basic Setup

```python
from dataclasses import dataclass
from predylogic import Registry


# Define your context type
@dataclass
class User:
    age: int
    email: str
    is_premium: bool


# Create a registry
user_registry = Registry[User]("user_registry")


# Register rule definitions using the decorator
@user_registry.rule_def()
def is_adult(user: User, min_age: int = 18) -> bool:
    """Check if user is at least min_age years old."""
    return user.age >= min_age


@user_registry.rule_def()
def is_premium(user: User) -> bool:
    """Check if user has premium status."""
    return user.is_premium


@user_registry.rule_def()
def is_email_verified(user: User, domain: str = "example.com") -> bool:
    """Check if user email is from a specific domain."""
    return user.email.endswith(f"@{domain}")
```

### Alternative: Direct Registration

If you prefer not to use decorators:

```python
def is_corporate_email(user: User, company_domain: str) -> bool:
    """Check if user has corporate email."""
    return user.email.endswith(f"@{company_domain}")


# Register with explicit name
producer = user_registry.register(is_corporate_email, "has_corporate_email")
```

### Multiple Context Types

You can create separate registries for different context types:

> Each context within a registry should be of the same type or satisfy LSP.

```python
from typing import TypedDict


class OrderContext(TypedDict):
    total: float
    item_count: int
    is_bulk: bool


order_registry = Registry[OrderContext]("order_registry")


@order_registry.rule_def()
def high_value_order(order: OrderContext, min_total: float = 1000.0) -> bool:
    return order["total"] >= min_total


@order_registry.rule_def()
def bulk_order(order: OrderContext) -> bool:
    return order["is_bulk"]
```

## 2. Exporting JSON Schemas

Once you've defined your rules, you can generate JSON schemas (by pydantic) for external configuration and validation.

### Generate Schema

```python
from predylogic import SchemaGenerator

# Create a schema generator
schema_gen = SchemaGenerator(user_registry)

# Generate the manifest pydantic model
UserManifest = schema_gen.generate()

# Export JSON schema
json_schema = UserManifest.model_json_schema()
print(json_schema)
```

### Using the Schema

The generated schema can be used to:

- Validate rule configurations in external systems
- Generate API documentation
- Create UI forms for rule configuration
- Ensure type safety for JSON inputs

??? Example output
	```json
	{
	  "$defs":{
		"AndNode_Union_IsAdultConfig__IsPremiumConfig__IsEmailVerifiedConfig__":{
		  "additionalProperties":false,
		  "properties":{
			"node_type":{
			  "const":"and",
			  "default":"and",
			  "description":"And node in the predicate tree",
			  "title":"Node Type",
			  "type":"string"
			},
			"rules":{
			  "description":"All rules must pass",
			  "items":{
				"$ref":"#/$defs/LogicNode_Union_IsAdultConfig__IsPremiumConfig__IsEmailVerifiedConfig__"
			  },
			  "minItems":2,
			  "title":"Rules",
			  "type":"array"
			}
		  },
		  "required":[
			"rules"
		  ],
		  "title":"AndNode",
		  "type":"object"
		},
		"IsAdultConfig":{
		  "additionalProperties":false,
		  "description":"Check if user is at least min_age years old.",
		  "properties":{
			"rule_def_name":{
			  "const":"is_adult",
			  "default":"is_adult",
			  "description":"Name of the rule definition in the registry",
			  "title":"Rule Def Name",
			  "type":"string"
			},
			"min_age":{
			  "default":18,
			  "title":"Min Age",
			  "type":"integer"
			}
		  },
		  "title":"IsAdultConfig",
		  "type":"object",
		  "x-params-order":[
			"min_age"
		  ]
		},
		"IsEmailVerifiedConfig":{
		  "additionalProperties":false,
		  "description":"Check if user email is from a specific domain.",
		  "properties":{
			"rule_def_name":{
			  "const":"is_email_verified",
			  "default":"is_email_verified",
			  "description":"Name of the rule definition in the registry",
			  "title":"Rule Def Name",
			  "type":"string"
			},
			"domain":{
			  "default":"example.com",
			  "title":"Domain",
			  "type":"string"
			}
		  },
		  "title":"IsEmailVerifiedConfig",
		  "type":"object",
		  "x-params-order":[
			"domain"
		  ]
		},
		"IsPremiumConfig":{
		  "additionalProperties":false,
		  "description":"Check if user has premium status.",
		  "properties":{
			"rule_def_name":{
			  "const":"is_premium",
			  "default":"is_premium",
			  "description":"Name of the rule definition in the registry",
			  "title":"Rule Def Name",
			  "type":"string"
			}
		  },
		  "title":"IsPremiumConfig",
		  "type":"object",
		  "x-params-order":[ ]
		},
		"LeafNode_Union_IsAdultConfig__IsPremiumConfig__IsEmailVerifiedConfig__":{
		  "additionalProperties":false,
		  "properties":{
			"node_type":{
			  "const":"leaf",
			  "default":"leaf",
			  "description":"Leaf node in the predicate tree",
			  "title":"Node Type",
			  "type":"string"
			},
			"rule":{
			  "anyOf":[
				{
				  "$ref":"#/$defs/IsAdultConfig"
				},
				{
				  "$ref":"#/$defs/IsPremiumConfig"
				},
				{
				  "$ref":"#/$defs/IsEmailVerifiedConfig"
				}
			  ],
			  "description":"The rule to evaluate",
			  "title":"Rule"
			}
		  },
		  "required":[
			"rule"
		  ],
		  "title":"LeafNode",
		  "type":"object"
		},
		"LogicNode_Union_IsAdultConfig__IsPremiumConfig__IsEmailVerifiedConfig__":{
		  "discriminator":{
			"mapping":{
			  "and":"#/$defs/AndNode_Union_IsAdultConfig__IsPremiumConfig__IsEmailVerifiedConfig__",
			  "leaf":"#/$defs/LeafNode_Union_IsAdultConfig__IsPremiumConfig__IsEmailVerifiedConfig__",
			  "not":"#/$defs/NotNode_Union_IsAdultConfig__IsPremiumConfig__IsEmailVerifiedConfig__",
			  "or":"#/$defs/OrNode_Union_IsAdultConfig__IsPremiumConfig__IsEmailVerifiedConfig__",
			  "ref":"#/$defs/RefNode_Union_IsAdultConfig__IsPremiumConfig__IsEmailVerifiedConfig__"
			},
			"propertyName":"node_type"
		  },
		  "oneOf":[
			{
			  "$ref":"#/$defs/LeafNode_Union_IsAdultConfig__IsPremiumConfig__IsEmailVerifiedConfig__"
			},
			{
			  "$ref":"#/$defs/AndNode_Union_IsAdultConfig__IsPremiumConfig__IsEmailVerifiedConfig__"
			},
			{
			  "$ref":"#/$defs/OrNode_Union_IsAdultConfig__IsPremiumConfig__IsEmailVerifiedConfig__"
			},
			{
			  "$ref":"#/$defs/NotNode_Union_IsAdultConfig__IsPremiumConfig__IsEmailVerifiedConfig__"
			},
			{
			  "$ref":"#/$defs/RefNode_Union_IsAdultConfig__IsPremiumConfig__IsEmailVerifiedConfig__"
			}
		  ],
		  "title":"LogicNode"
		},
		"NotNode_Union_IsAdultConfig__IsPremiumConfig__IsEmailVerifiedConfig__":{
		  "additionalProperties":false,
		  "properties":{
			"node_type":{
			  "const":"not",
			  "default":"not",
			  "description":"Not node in the predicate tree",
			  "title":"Node Type",
			  "type":"string"
			},
			"rule":{
			  "$ref":"#/$defs/LogicNode_Union_IsAdultConfig__IsPremiumConfig__IsEmailVerifiedConfig__",
			  "description":"The rule must fail"
			}
		  },
		  "required":[
			"rule"
		  ],
		  "title":"NotNode",
		  "type":"object"
		},
		"OrNode_Union_IsAdultConfig__IsPremiumConfig__IsEmailVerifiedConfig__":{
		  "additionalProperties":false,
		  "properties":{
			"node_type":{
			  "const":"or",
			  "default":"or",
			  "description":"Or node in the predicate tree",
			  "title":"Node Type",
			  "type":"string"
			},
			"rules":{
			  "description":"Any rule must pass",
			  "items":{
				"$ref":"#/$defs/LogicNode_Union_IsAdultConfig__IsPremiumConfig__IsEmailVerifiedConfig__"
			  },
			  "minItems":2,
			  "title":"Rules",
			  "type":"array"
			}
		  },
		  "required":[
			"rules"
		  ],
		  "title":"OrNode",
		  "type":"object"
		},
		"RefNode_Union_IsAdultConfig__IsPremiumConfig__IsEmailVerifiedConfig__":{
		  "additionalProperties":false,
		  "properties":{
			"node_type":{
			  "const":"ref",
			  "default":"ref",
			  "description":"Reference to a rule definition",
			  "title":"Node Type",
			  "type":"string"
			},
			"ref_id":{
			  "description":"Rule definition ID",
			  "title":"Ref Id",
			  "type":"string"
			}
		  },
		  "required":[
			"ref_id"
		  ],
		  "title":"RefNode[Union[IsAdultConfig, IsPremiumConfig, IsEmailVerifiedConfig]]",
		  "type":"object"
		}
	  },
	  "additionalProperties":false,
	  "properties":{
		"registry":{
		  "const":"user_registry",
		  "default":"user_registry",
		  "description":"Name of the registry containing the rule definitions",
		  "title":"Registry",
		  "type":"string"
		},
		"rules":{
		  "additionalProperties":{
			"$ref":"#/$defs/LogicNode_Union_IsAdultConfig__IsPremiumConfig__IsEmailVerifiedConfig__"
		  },
		  "description":"Dag of rule definitions.",
		  "title":"Rules",
		  "type":"object"
		}
	  },
	  "title":"UserRegistryManifest",
	  "type":"object"
	}
	```

## 3. Importing Configurations

Create rule configurations from JSON data and validate them against the generated schema.

### Simple Configuration

```python
from predylogic import RuleEngine
from predylogic.rule_engine.base import LeafNode

# Create a manifest
manifest = UserManifest(
    rules={
        "is_adult_rule": LeafNode(
            rule={
                "rule_def_name": "is_adult",
                "min_age": 21,
            }
        ),
        "is_premium_rule": LeafNode(
            rule={
                "rule_def_name": "is_premium",
            }
        ),
    }
)

# Manifest is automatically validated against schema
assert manifest.registry == "user_registry"
```

### Complex Configuration (Logical Composition)

```python
from predylogic.rule_engine.base import AndNode, OrNode, NotNode, RefNode

# Create composite rules
manifest = UserManifest(
    rules={
        "premium_adult": AndNode(
            rules=[
                LeafNode(rule={"rule_def_name": "is_adult", "min_age": 18}),
                LeafNode(rule={"rule_def_name": "is_premium"}),
            ]
        ),
        "verified_email": LeafNode(
            rule={
                "rule_def_name": "is_email_verified",
                "domain": "company.com",
            }
        ),
        "special_users": OrNode(
            rules=[
                RefNode(ref_id="premium_adult"),
                RefNode(ref_id="verified_email"),
            ]
        ),
    }
)
```

### Loading from JSON

```python
import json

# Load configuration from file or API
config_data = {
    "rules": {
        "adult_check": {
            "node_type": "leaf",
            "rule": {"rule_def_name": "is_adult", "min_age": 21}
        },
        "premium_check": {
            "node_type": "leaf",
            "rule": {"rule_def_name": "is_premium"}
        },
        "premium_adults": {
            "node_type": "and",
            "rules": [
                {"node_type": "ref", "ref_id": "adult_check"},
                {"node_type": "ref", "ref_id": "premium_check"},
            ]
        }
    }
}

# Validate and create manifest
manifest = UserManifest(**config_data)
```

## 4. Retrieving Predicates at Runtime

Use the **RuleEngine** to execute rules dynamically at runtime.

### Basic Execution

```python
from predylogic import RegistryManager
from predylogic.rule_engine import RuleEngine

# Set up manager and engine
registry_manager = RegistryManager()
registry_manager.add_register(user_registry)

engine = RuleEngine(registry_manager)
engine.update_manifests(manifest)

# Get a predicate handle
is_adult_handle = engine.get_predicate_handle("user_registry", "adult_check")

# Execute the predicate
user = User(age=25, email="alice@example.com", is_premium=True)
result = is_adult_handle(user)  # Returns: True
```

### Executing Complex Rules

```python
# Get handle for composite rule
special_users_handle = engine.get_predicate_handle("user_registry", "special_users")

# Execute
result = special_users_handle(user)  # Returns: True/False
```

### Hot Reloading

Update rules at runtime without recreating handles:

```python
# Update manifest with new rules
new_manifest = UserManifest(
    rules={
        "adult_check": LeafNode(
            rule={"rule_def_name": "is_adult", "min_age": 25}
        ),
    }
)

engine.update_manifests(new_manifest)

# Same handle, updated behavior
is_adult_handle = engine.get_predicate_handle("user_registry", "adult_check")
result = is_adult_handle(user)  # Now uses min_age=25
```

### Multiple Registries

```python
order_schema = SchemaGenerator(order_registry).generate()

order_manifest = order_schema(
    rules={
        "high_value": LeafNode(
            rule={"rule_def_name": "high_value_order", "min_total": 5000.0}
        ),
    }
)

registry_manager.add_register(order_registry)
engine.update_manifests(manifest, order_manifest)

# Access rules from different registries
user_handle = engine.get_predicate_handle("user_registry", "adult_check")
order_handle = engine.get_predicate_handle("order_registry", "high_value")
```

## 5. Manually Composing Predicates

For dynamic or programmatic composition, create predicates directly without manifests.

### Basic Composition

```python
from predylogic import predicate

# Create basic predicates
is_adult = predicate(lambda user: user.age >= 18, name="is_adult")
is_premium = predicate(lambda user: user.is_premium, name="is_premium")

# Compose using operators
premium_adult = is_adult & is_premium
not_premium = ~is_premium
adult_or_premium = is_adult | is_premium

# Execute
user = User(age=25, email="alice@example.com", is_premium=True)
result = premium_adult(user)  # Returns: True
```

### Using ComposablePredicate

```python
from predylogic import ComposablePredicate

# Create predicates from registry
adult_producer = user_registry["is_adult"]
premium_producer = user_registry["is_premium"]

# Produce predicates with parameters
is_adult_21 = adult_producer(min_age=21)
is_premium_check = premium_producer()

# Compose
special_user = is_adult_21 & is_premium_check

# Execute
result = special_user(user)
```

### Logical Operators

```python
# AND - all conditions must be true
condition_and = predicate1 & predicate2 & predicate3

# OR - at least one condition must be true
condition_or = predicate1 | predicate2 | predicate3

# NOT - negate the condition
condition_not = ~predicate1

# Complex expressions
complex_logic = (predicate1 & predicate2) | (~predicate3)

# Execute
result = complex_logic(context)
```

### Trace Execution

Get detailed execution traces for debugging:

```python
# Execute with trace
is_adult = predicate(lambda user: user.age >= 18, name="is_adult")
is_premium = predicate(lambda user: user.is_premium, name="is_premium")
combined = is_adult & is_premium

user = User(age=25, email="alice@example.com", is_premium=True)
trace = combined(user, trace=True)  # Returns Trace object instead of bool

# Inspect the trace
print(f"Operator: {trace.operator}")  # "and"
print(f"Success: {trace.success}")  # True
print(f"Children: {trace.children}")  # [Trace, Trace]

# Print detailed trace
print(repr(trace))
```

### Short-Circuit Evaluation

```python
# Control whether evaluation stops early
combined = predicate1 & predicate2

# With short-circuit (default for bool results)
result = combined(user, short_circuit=True)  # Stops if predicate1 is False

# Full evaluation (useful for traces)
trace = combined(user, trace=True, short_circuit=False)  # Evaluates both
```

## Complete Example

Here's a complete example bringing everything together:

```python
from dataclasses import dataclass
from predylogic import (
    Registry, RegistryManager, SchemaGenerator,
    RuleEngine, predicate
)
from predylogic.rule_engine.base import LeafNode, AndNode


# 1. Define context
@dataclass
class User:
    age: int
    email: str
    is_premium: bool


# 2. Create registry and register rules
user_registry = Registry[User]("user_registry")


@user_registry.rule_def()
def is_adult(user: User, min_age: int = 18) -> bool:
    return user.age >= min_age


@user_registry.rule_def()
def is_premium(user: User) -> bool:
    return user.is_premium


# 3. Generate schema
schema_gen = SchemaGenerator(user_registry)
UserManifest = schema_gen.generate()

# 4. Create configuration
manifest = UserManifest(
    rules={
        "adult": LeafNode(rule={"rule_def_name": "is_adult", "min_age": 21}),
        "premium": LeafNode(rule={"rule_def_name": "is_premium"}),
        "vip_users": AndNode(
            rules=[
                LeafNode(rule={"rule_def_name": "is_adult", "min_age": 21}),
                LeafNode(rule={"rule_def_name": "is_premium"}),
            ]
        ),
    }
)

# 5. Set up engine and execute
registry_manager = RegistryManager()
registry_manager.add_register(user_registry)

engine = RuleEngine(registry_manager)
engine.update_manifests(manifest)

# Get predicates
vip_check = engine.get_predicate_handle("user_registry", "vip_users")

# Execute
user = User(age=25, email="alice@example.com", is_premium=True)
is_vip = vip_check(user)  # True

# Or compose manually
is_adult = predicate(lambda u: u.age >= 21, name="is_adult")
is_premium = predicate(lambda u: u.is_premium, name="is_premium")
vip_manual = is_adult & is_premium

is_vip_manual = vip_manual(user)  # True
```

## Next Steps

- Read the [Modules](modules.md) documentation for detailed API reference
- Explore [Design & Architecture](design/index.md) for implementation details
- Check out the test suite for more usage examples

## Common Patterns

### Dynamic Rule Building

```python
def create_age_rule(min_age: int):
    return predicate(
        lambda user: user.age >= min_age,
        name=f"min_age_{min_age}"
    )


rule_18 = create_age_rule(18)
rule_21 = create_age_rule(21)
```

### Conditional Composition

```python
def build_user_filter(require_premium=False, min_age=18):
    is_adult = predicate(lambda u: u.age >= min_age, name="is_adult")

    if require_premium:
        is_premium = predicate(lambda u: u.is_premium, name="is_premium")
        return is_adult & is_premium
    else:
        return is_adult


filter_vip = build_user_filter(require_premium=True, min_age=21)
filter_standard = build_user_filter(require_premium=False, min_age=18)
```

### Batch Execution

```python
users = [
    User(age=25, email="alice@example.com", is_premium=True),
    User(age=16, email="bob@example.com", is_premium=False),
    User(age=30, email="charlie@example.com", is_premium=True),
]

vip_check = engine.get_predicate_handle("user_registry", "vip_users")

vip_users = [u for u in users if vip_check(u)]
```

Happy building with Predylogic! 🚀
