# Merge Vector Layers - QGIS Plugin

[![QGIS Plugin](https://img.shields.io/badge/QGIS-Plugin-589632?style=flat&logo=qgis)](https://qgis.org)
[![Version](https://img.shields.io/badge/version-1.0-blue.svg)](https://github.com/viquezr-dev/unir_capas_plugin)
[![License](https://img.shields.io/badge/license-GPLv2-green.svg)](https://www.gnu.org/licenses/gpl-2.0.html)
[![Python](https://img.shields.io/badge/python-3.9%2B-yellow.svg)](https://www.python.org/)

**Merge Vector Layers** is a QGIS plugin that allows you to merge multiple vector layers (Shapefile, GeoPackage, etc.) into a single layer, with automatic CRS transformation and intelligent field handling.

## ✨ Key Features

- 🔄 **Merge multiple layers** into one single file
- 🗺️ **Automatic CRS transformation** when layers have different coordinate systems
- 📋 **Intelligent field handling** with maximum length option
- 📊 **Real-time progress bar** with detailed feedback
- 💾 **Multiple output formats** (Shapefile .shp or GeoPackage .gpkg)
- 🎨 **Intuitive interface** with visual layer selection
- 📍 **Supports all geometry types** (points, lines, polygons)
- ⚡ **Background processing** (doesn't freeze QGIS interface)

## 📋 Requirements

- **QGIS** version 3.0 or higher
- **Python** 3.9+
- Vector layers (points, lines, or polygons)

## 🚀 Installation

### From the official QGIS repository (coming soon)
1. Open QGIS → Plugins → Manage and Install Plugins
2. Search for "Merge Vector Layers"
3. Click "Install"

### Manual installation from GitHub
1. Download the repository as ZIP

2. Extract to the QGIS plugins folder:
- **Windows**: `C:\Users\YOUR_USER\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\`
- **Linux**: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
- **macOS**: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`

3. Rename the folder to `merge_layers`

4. Restart QGIS

5. Activate the plugin in Plugins → Manage Plugins

## 🎯 How to Use

### Step by step

1. **Load** the vector layers you want to merge in QGIS

2. **Open the plugin**: Toolbar button or `Plugins → Merge Vector Layers`

3. **Select layers to merge**:
- ✓ Check the boxes next to the layers you want to merge
- Use "All" to select all layers
- Use "Clear" to deselect all
- Use "Refresh" to update the layer list

4. **Configure options** (optional):
- ✓ **Use maximum field length**: Adapts field lengths to the maximum value found across all layers

5. **Choose output file**:
- Click "Browse" to select location and format
- Supported formats: Shapefile (.shp) or GeoPackage (.gpkg)

6. **Click "MERGE LAYERS"** to start the process

7. **Review results** in the log panel and map canvas

### CRS Handling

The plugin intelligently handles different CRS:

- **All layers same CRS**: Uses that CRS for output
- **Different CRS detected**: Shows dialog to choose:
- EPSG:32617 (WGS 84 / UTM zone 17N)
- First layer's CRS
- Cancel and fix manually

> 💡 **Note**: The merged layer is automatically added to your project and ready to use!

## 📊 Results Visualization

| Generated content | Description |
|-------------------|-------------|
| **Merged layer** | Final layer with all geometries combined |
| **Progress bar** | Shows real-time processing status |
| **Detailed log** | Information about CRS transformations and statistics |

## ⚙️ Technical Details

### Field Handling

- Preserves all fields from all layers
- Fields with same name are merged into one column
- Missing values are left as NULL
- Option to use maximum field length across all layers

### Supported Formats

| Format | Extension | Support |
|--------|-----------|---------|
| Shapefile | .shp | ✅ Full |
| GeoPackage | .gpkg | ✅ Full |
| Other vector formats | - | Via QGIS native layers |

### CRS Transformation

- Uses QGIS transformation engine
- Preserves geometric accuracy
- Automatic reprojection when needed

## 🛠️ Development

### Plugin Structure
merge_layers/
├── init.py # Plugin initialization
├── merge_layers_main.py # Main code
├── metadata.txt # Metadata for QGIS
└── icon.png # Plugin icon (64x64)


### Technologies Used
- **PyQt5** - Graphical interface
- **QGIS Python API** - Layer and geometry manipulation
- **QThread** - Background processing
- **GDAL/OGR** - Vector format handling

## 🐛 Bug Reporting

If you find any issues or have suggestions:

1. Check the [existing issues](https://github.com/viquezr-dev/unir_capas_plugin/issues)
2. Open a new issue describing:
   - QGIS version
   - Layer types and formats
   - CRS of each layer
   - Steps to reproduce the error
   - Screenshots (if applicable)

## 📝 Changelog

### Version 1.0 (Stable) - 2026
- ✨ Initial stable release
- 🔄 Multiple layer merging support
- 🗺️ Automatic CRS transformation
- 📋 Intelligent field handling
- 📊 Progress bar with detailed feedback
- 💾 Shapefile and GeoPackage support
- 🎨 Modern, intuitive interface
- ⚡ Background processing thread

## 👨‍💻 Author

**Raúl Viquez**
- GitHub: [@viquezr](https://github.com/viquezr-dev/unir_capas_plugin)
- Email: viquezr@gmail.com

## 📄 License

This plugin is licensed under the **GNU General Public License v2.0**.  
See the [LICENSE](LICENSE) file for more details.

## 🙏 Acknowledgments

- QGIS community for excellent documentation
- Contributors who report issues and suggest improvements
- GDAL/OGR developers for robust format support

---

## 💡 Tips & Tricks

### Performance Optimization
- For large datasets, consider merging in batches
- Use GeoPackage for better performance with large files
- Close unused layers before merging to save memory

### Common Use Cases
1. **Combining adjacent map sheets** into a single layer
2. **Merging seasonal data** (e.g., vegetation indices from different dates)
3. **Consolidating multiple surveys** into one master dataset
4. **Preparing data for export** to other software

### Troubleshooting

**Problem**: "Different CRS detected" warning  
**Solution**: Choose the appropriate CRS for your project or pre-convert layers manually

**Problem**: Very slow merging  
**Solution**: Consider using GeoPackage format and reducing the number of fields

**Problem**: Field lengths are too short  
**Solution**: Enable "Use maximum field length" option

---

**Do you like the plugin?**  
⭐ Give it a star on GitHub!  
🐛 Found a bug? Open an [issue](https://github.com/viquezr-dev/unir_capas_plugin/issues)

---

## 🔗 Useful Links

- [QGIS Documentation](https://qgis.org/docs/)
- [Coordinate Systems - EPSG](https://epsg.io/)
- [PyQGIS API Reference](https://qgis.org/pyqgis/)
- [GDAL Documentation](https://gdal.org/)

**Happy merging!** 🗺️✨
