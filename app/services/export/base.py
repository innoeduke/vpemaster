from .formatter import ExportFormatter


class BaseExportComponent:
    """Base class for a data table component within a sheet."""
    def render(self, ws, context, start_row):
        raise NotImplementedError


class BaseExportBoard:
    """Base class for a worksheet board composed of components."""
    def __init__(self, title):
        self.title = title
        self.components = []

    def add_component(self, component):
        self.components.append(component)

    def render(self, ws, context):
        ws.title = self.title
        current_row = 1
        for component in self.components:
            current_row = component.render(ws, context, current_row)
        # Auto-fit is now handled at component level
