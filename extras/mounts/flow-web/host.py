"""Supply the native HTTP foot address; flow execution stays in the namespace."""


def prepare(root, work, check, cleanup, context):
    return root, [f'/{context["node"]}/io/web']
