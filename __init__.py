"""
Unir Capas Vectoriales
Un plugin para QGIS que permite unir múltiples capas vectoriales en una sola
"""

def classFactory(iface):
    from .unir_capas import UnirCapasPlugin
    return UnirCapasPlugin(iface)