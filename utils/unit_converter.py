def convert_units(value, units):
    """Convert the value based on the units provided."""
    if units == 'mm':
        return value / 1000.0
    elif units == 'cm':
        return value / 100.0
    elif units == 'm':
        return value
    else:
        raise ValueError(f"Units '{units}' not recognized. Supported units are 'mm', 'cm', 'm'.")