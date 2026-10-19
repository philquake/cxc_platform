from django import template

register = template.Library()


@register.simple_tag
def a11y_field(field):
	"""Render a form field with aria attributes tying it to its help text and errors."""
	described_by = []
	attrs = {}
	if field.help_text:
		described_by.append(f"{field.auto_id}-help")
	if field.errors:
		described_by.append(f"{field.auto_id}-errors")
		attrs["aria-invalid"] = "true"
	if described_by:
		attrs["aria-describedby"] = " ".join(described_by)
	return field.as_widget(attrs=attrs)
