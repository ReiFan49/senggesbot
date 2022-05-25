import contextlib

@contextlib.contextmanager
def swap_variable(obj, key, new_value):
  old_value = getattr(obj, key)
  setattr(obj, key, new_value)
  try:
    yield obj
  finally:
    setattr(obj, key, old_value)
