"""Locate and load template-schema.json.

The user's copy under ~/.expense-claim-review/templates/ wins over the one shipped
with the plugin, so overriding a column there changes what the validators accept.
"""
import json
import os


def schema_path(explicit=None):
    if explicit:
        return explicit
    user = os.path.expanduser("~/.expense-claim-review/templates/template-schema.json")
    if os.path.exists(user):
        return user
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, os.pardir, "templates", "template-schema.json")


def load(explicit=None):
    path = schema_path(explicit)
    with open(path) as f:
        return json.load(f), path


def columns(spec):
    return [c["name"] for c in spec["columns"]]


def required(spec):
    return [c["name"] for c in spec["columns"] if c.get("required")]


def enum(schema, name):
    return schema["enums"][name]
