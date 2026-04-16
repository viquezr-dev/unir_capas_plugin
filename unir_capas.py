# -*- coding: utf-8 -*-
"""
unir_capas - Plugin para QGIS
Desarrollado por Raul Viquez (viquezr@gmail.com)
Version: 1.0 - Diseño completo
"""

from qgis.PyQt.QtWidgets import (QAction, QDialog, QVBoxLayout, QHBoxLayout, 
                                QLabel, QPushButton, QProgressBar, QListWidget,
                                QMessageBox, QGroupBox, QFileDialog, QCheckBox,
                                QListWidgetItem, QFrame, QWidget, QStackedWidget,
                                QGridLayout, QSpacerItem, QSizePolicy, QApplication)
from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from qgis.PyQt.QtGui import QColor, QIcon, QFont
from qgis.core import (QgsVectorLayer, QgsProject, QgsVectorFileWriter, 
                      QgsFields, QgsField, QgsFeature, QgsWkbTypes,
                      QgsGeometry, QgsCoordinateTransform, QgsCoordinateReferenceSystem)
from qgis.utils import iface
import os
import traceback

# ============================================================================
# THREAD PARA UNIÓN DE CAPAS
# ============================================================================

class UnirCapasThread(QThread):
    progress_updated = pyqtSignal(int, str)
    finished_process = pyqtSignal(bool, str, dict)

    def __init__(self, capas_seleccionadas, output_path, usar_longitud_maxima=True, crs_destino=None):
        super().__init__()
        self.capas_seleccionadas = capas_seleccionadas
        self.output_path = output_path
        self.usar_longitud_maxima = usar_longitud_maxima
        self.crs_destino = crs_destino

    def run(self):
        estadisticas = {
            'capas_procesadas': 0,
            'caracteristicas_unidas': 0,
            'campos_resultantes': 0,
            'tamano_archivo': 0,
            'errores': 0,
            'transformaciones_crs': 0
        }
        
        try:
            if not self.capas_seleccionadas:
                self.finished_process.emit(False, "No hay capas seleccionadas", estadisticas)
                return

            capas_validas = []
            for capa_info in self.capas_seleccionadas:
                capa = QgsProject.instance().mapLayer(capa_info['id'])
                if capa and capa.isValid():
                    capas_validas.append(capa)

            if not capas_validas:
                self.finished_process.emit(False, "No hay capas válidas para unir", estadisticas)
                return

            self.progress_updated.emit(5, "🔍 Analizando CRS de las capas...")

            if self.crs_destino is None or not self.crs_destino.isValid():
                self.crs_destino = capas_validas[0].crs()

            transformadores = []
            crs_diferentes = []
            for capa in capas_validas:
                if capa.crs().authid() != self.crs_destino.authid():
                    crs_diferentes.append(capa.name())
                    estadisticas['transformaciones_crs'] += 1
                    transform_context = QgsProject.instance().transformContext()
                    transformador = QgsCoordinateTransform(capa.crs(), self.crs_destino, transform_context)
                    transformadores.append(transformador)
                else:
                    transformadores.append(None)
            
            self.progress_updated.emit(10, "🔍 Analizando estructura de campos...")

            estructura_campos = {}
            mapas_campos_por_capa = []
            tipo_geometria = QgsWkbTypes.Unknown

            for capa in capas_validas:
                mapa_campos = {}
                fields = capa.fields()
                for j in range(fields.count()):
                    field = fields.at(j)
                    field_name = field.name()
                    mapa_campos[field_name] = j
                    
                    if field_name not in estructura_campos:
                        estructura_campos[field_name] = {
                            'type': field.type(),
                            'length': field.length(),
                            'precision': field.precision(),
                            'type_name': field.typeName()
                        }
                    elif self.usar_longitud_maxima:
                        if field.length() > estructura_campos[field_name]['length']:
                            estructura_campos[field_name]['length'] = field.length()
                            estructura_campos[field_name]['precision'] = field.precision()
                
                mapas_campos_por_capa.append(mapa_campos)
                
                geom_type = capa.wkbType()
                if tipo_geometria == QgsWkbTypes.Unknown:
                    tipo_geometria = geom_type
                elif geom_type != QgsWkbTypes.Unknown:
                    base_type = QgsWkbTypes.flatType(geom_type)
                    current_base = QgsWkbTypes.flatType(tipo_geometria)
                    if base_type != current_base:
                        tipo_geometria = QgsWkbTypes.Unknown

            if not estructura_campos:
                self.finished_process.emit(False, "No se encontraron campos en las capas", estadisticas)
                return

            self.progress_updated.emit(30, f"⚙️ Creando capa de salida con {len(estructura_campos)} campos...")

            fields_final = QgsFields()
            indices_campos_finales = {}
            
            for field_name, info in estructura_campos.items():
                try:
                    new_field = QgsField(field_name, info['type'], len=info['length'], prec=info['precision'])
                    fields_final.append(new_field)
                    indices_campos_finales[field_name] = fields_final.count() - 1
                except Exception as e:
                    try:
                        new_field = QgsField(field_name, info['type'])
                        fields_final.append(new_field)
                        indices_campos_finales[field_name] = fields_final.count() - 1
                    except:
                        print(f"No se pudo crear el campo {field_name}")

            if fields_final.count() == 0:
                self.finished_process.emit(False, "No se pudieron crear campos", estadisticas)
                return

            self.progress_updated.emit(40, "💾 Guardando archivo de salida...")
            
            options = QgsVectorFileWriter.SaveVectorOptions()
            options.fileEncoding = "UTF-8"
            
            if self.output_path.lower().endswith('.gpkg'):
                options.driverName = "GPKG"
                options.layerName = os.path.splitext(os.path.basename(self.output_path))[0]
            else:
                options.driverName = "ESRI Shapefile"
                if not self.output_path.lower().endswith('.shp'):
                    self.output_path += '.shp'

            writer = QgsVectorFileWriter.create(
                self.output_path,
                fields_final,
                tipo_geometria,
                self.crs_destino,  
                QgsProject.instance().transformContext(),
                options
            )

            if writer.hasError():
                error_msg = writer.errorMessage()
                del writer
                self.finished_process.emit(False, f"❌ Error creando archivo: {error_msg}", estadisticas)
                return

            self.progress_updated.emit(45, "🔄 Uniendo características...")
            
            total_caracteristicas = sum(capa.featureCount() for capa in capas_validas)
            if total_caracteristicas == 0:
                total_caracteristicas = 1

            caracteristicas_procesadas = 0
            errores = 0

            for capa_idx, capa in enumerate(capas_validas):
                mapa_origen = mapas_campos_por_capa[capa_idx]
                transformador = transformadores[capa_idx]
                features = capa.getFeatures()
                
                for feature in features:
                    try:
                        nueva_feature = QgsFeature(fields_final)
                        
                        if feature.hasGeometry():
                            geom = feature.geometry()
                            if transformador is not None:
                                geom.transform(transformador)
                            nueva_feature.setGeometry(geom)
                        
                        for campo_final, idx_final in indices_campos_finales.items():
                            if campo_final in mapa_origen:
                                idx_origen = mapa_origen[campo_final]
                                valor = feature.attribute(idx_origen)
                                nueva_feature.setAttribute(idx_final, valor)
                        
                        if not writer.addFeature(nueva_feature):
                            errores += 1
                        else:
                            caracteristicas_procesadas += 1
                            
                    except Exception as e:
                        errores += 1
                        continue

                    if caracteristicas_procesadas % 250 == 0:
                        progreso = 45 + int((caracteristicas_procesadas / total_caracteristicas) * 45)
                        progreso = min(progreso, 90)
                        porcentaje = (caracteristicas_procesadas / total_caracteristicas) * 100
                        self.progress_updated.emit(progreso, f"✅ {caracteristicas_procesadas:,}/{total_caracteristicas:,} ({porcentaje:.1f}%)")

            del writer

            self.progress_updated.emit(95, "✅ Verificando resultado...")

            if not os.path.exists(self.output_path):
                self.finished_process.emit(False, "❌ No se creó el archivo de salida", estadisticas)
                return

            tamano = os.path.getsize(self.output_path)
            if tamano < 1024:
                tamano_str = f"{tamano} bytes"
            elif tamano < 1048576:
                tamano_str = f"{tamano/1024:.1f} KB"
            else:
                tamano_str = f"{tamano/1048576:.1f} MB"
            
            estadisticas.update({
                'capas_procesadas': len(capas_validas),
                'caracteristicas_unidas': caracteristicas_procesadas,
                'campos_resultantes': fields_final.count(),
                'tamano_archivo': tamano_str,
                'errores': errores
            })

            nombre_capa = os.path.splitext(os.path.basename(self.output_path))[0]
            capa_resultado = QgsVectorLayer(self.output_path, nombre_capa, "ogr")
            
            if capa_resultado.isValid():
                QgsProject.instance().addMapLayer(capa_resultado)
                
                mensaje = f"✨ ¡Unión completada con éxito!\n\n"
                mensaje += f"📊 Capas procesadas: {len(capas_validas)}\n"
                mensaje += f"📍 Features unidas: {caracteristicas_procesadas:,}\n"
                mensaje += f"📋 Campos totales: {fields_final.count()}\n"
                mensaje += f"💾 Tamaño archivo: {tamano_str}\n"
                mensaje += f"📐 CRS destino: {self.crs_destino.authid()}"
                
                if estadisticas['transformaciones_crs'] > 0:
                    mensaje += f"\n🔄 Capas transformadas: {estadisticas['transformaciones_crs']}"
                
                if errores > 0:
                    mensaje += f"\n⚠️ Errores durante el proceso: {errores}"
                
                self.progress_updated.emit(100, "🎉 ¡Proceso completado!")
                self.finished_process.emit(True, mensaje, estadisticas)
            else:
                self.finished_process.emit(False, "⚠️ La capa se creó pero no se pudo cargar en el proyecto", estadisticas)

        except Exception as e:
            error_detallado = traceback.format_exc()
            print(f"Error en thread: {error_detallado}")
            self.finished_process.emit(False, f"❌ Error inesperado: {str(e)[:200]}", estadisticas)


# ============================================================================
# DIÁLOGO PRINCIPAL
# ============================================================================

class UnirCapasDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔄 Unir Capas Vectoriales")
        self.setFixedSize(700, 550)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        self.capas_seleccionadas = []
        self.output_path = ""
        self.thread = None
        
        self.setup_ui()
        
    def setup_ui(self):
        """Configura la interfaz de usuario - Estilo profesional fusionado"""
        main_layout = QVBoxLayout()
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # === TÍTULO PRINCIPAL ===
        title_widget = QWidget()
        title_widget.setFixedHeight(45)
        title_widget.setStyleSheet("""
            QWidget {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                                                 stop:0 #134e4a, stop:1 #0d9488);
                border-radius: 6px;
            }
        """)
        title_layout = QHBoxLayout(title_widget)
        title_layout.setContentsMargins(12, 0, 12, 0)

        title_icon = QLabel("🔄")
        title_icon.setStyleSheet("font-size: 18px; color: white;")
        title_layout.addWidget(title_icon)

        title_text = QLabel("Unir Capas Vectoriales")
        title_text.setStyleSheet("font-size: 14px; font-weight: bold; color: white;")
        title_layout.addWidget(title_text)

        version_label = QLabel("v1.0")
        version_label.setStyleSheet("""
            color: rgba(255,255,255,0.8);
            font-size: 9px;
            padding: 2px 8px;
            background-color: rgba(0,0,0,0.2);
            border-radius: 10px;
        """)
        title_layout.addWidget(version_label)
        title_layout.addStretch()
        main_layout.addWidget(title_widget)

        # === 1. GRUPO CAPAS ===
        layer_group = QGroupBox("📋 1. Capas a unir")
        layer_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #0d9488;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 8px;
                font-size: 11px;
                background-color: white;
            }
            QGroupBox::title {
                left: 10px;
                padding: 0 8px 0 8px;
                color: #0d9488;
            }
        """)
        layer_layout = QVBoxLayout()
        layer_layout.setContentsMargins(8, 5, 8, 8)
        layer_layout.setSpacing(6)

        self.lista_capas = QListWidget()
        self.lista_capas.setMinimumHeight(200)
        self.lista_capas.setStyleSheet("""
            QListWidget {
                border: 1px solid #e2e8f0;
                border-radius: 4px;
                padding: 4px;
                background-color: white;
                font-size: 11px;
                outline: none;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #f1f5f9;
            }
            QListWidget::item:hover {
                background-color: #f0fdfa;
            }
        """)
        self.lista_capas.setSelectionMode(QListWidget.NoSelection)
        layer_layout.addWidget(self.lista_capas)

        # Botones
        btn_container = QHBoxLayout()
        btn_container.setSpacing(6)

        self.btn_agregar_todas = QPushButton("✓ Todas")
        self.btn_agregar_todas.setFixedHeight(26)
        self.btn_agregar_todas.setStyleSheet("""
            QPushButton {
                background-color: #0d9488;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover { background-color: #0f766e; }
        """)
        self.btn_agregar_todas.clicked.connect(self.agregar_todas_las_capas)

        self.btn_limpiar = QPushButton("✗ Limpiar")
        self.btn_limpiar.setFixedHeight(26)
        self.btn_limpiar.setStyleSheet("""
            QPushButton {
                background-color: #e76f51;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover { background-color: #d45a3a; }
        """)
        self.btn_limpiar.clicked.connect(self.limpiar_seleccion)

        self.btn_refrescar = QPushButton("↻ Refrescar")
        self.btn_refrescar.setFixedHeight(26)
        self.btn_refrescar.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover { background-color: #5a6268; }
        """)
        self.btn_refrescar.clicked.connect(self.refrescar_lista_capas)

        self.contador_label = QLabel("0 seleccionadas")
        self.contador_label.setAlignment(Qt.AlignCenter)
        self.contador_label.setFixedHeight(26)
        self.contador_label.setStyleSheet("""
            background-color: #f0fdfa;
            border: 1px solid #0d9488;
            border-radius: 12px;
            padding: 4px 12px;
            color: #0d9488;
            font-weight: bold;
            font-size: 10px;
        """)

        btn_container.addWidget(self.btn_agregar_todas)
        btn_container.addWidget(self.btn_limpiar)
        btn_container.addWidget(self.btn_refrescar)
        btn_container.addStretch()
        btn_container.addWidget(self.contador_label)

        layer_layout.addLayout(btn_container)
        layer_group.setLayout(layer_layout)
        main_layout.addWidget(layer_group)

        # === 2. GRUPO OPCIONES ===
        options_group = QGroupBox("⚙️ 2. Opciones")
        options_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #f4a261;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 8px;
                font-size: 11px;
                background-color: white;
            }
            QGroupBox::title {
                left: 10px;
                padding: 0 8px 0 8px;
                color: #f4a261;
            }
        """)
        options_layout = QHBoxLayout()
        options_layout.setContentsMargins(10, 5, 10, 8)

        self.check_longitud_maxima = QCheckBox("Usar longitud máxima de campos")
        self.check_longitud_maxima.setChecked(True)
        self.check_longitud_maxima.setStyleSheet("""
            QCheckBox {
                spacing: 8px;
                font-size: 11px;
                color: #334155;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 2px solid #f4a261;
                background: white;
            }
            QCheckBox::indicator:checked {
                background-color: #f4a261;
            }
        """)
        options_layout.addWidget(self.check_longitud_maxima)
        options_layout.addStretch()

        options_group.setLayout(options_layout)
        main_layout.addWidget(options_group)

        # === 3. GRUPO ARCHIVO SALIDA ===
        output_group = QGroupBox("💾 3. Guardar como")
        output_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #2a9d8f;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 8px;
                font-size: 11px;
                background-color: white;
            }
            QGroupBox::title {
                left: 10px;
                padding: 0 8px 0 8px;
                color: #2a9d8f;
            }
        """)
        output_layout = QHBoxLayout()
        output_layout.setContentsMargins(10, 5, 10, 8)
        output_layout.setSpacing(8)

        self.ruta_label = QLabel("📁 Ningún archivo seleccionado")
        self.ruta_label.setStyleSheet("""
            QLabel {
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 11px;
                font-family: monospace;
                color: #475569;
            }
        """)
        output_layout.addWidget(self.ruta_label, 1)

        self.btn_examinar = QPushButton("📂 Examinar")
        self.btn_examinar.setFixedHeight(30)
        self.btn_examinar.setFixedWidth(100)
        self.btn_examinar.setStyleSheet("""
            QPushButton {
                background-color: #2a9d8f;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 12px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover { background-color: #21867a; }
        """)
        self.btn_examinar.clicked.connect(self.seleccionar_archivo_salida)

        output_layout.addWidget(self.btn_examinar)
        output_group.setLayout(output_layout)
        main_layout.addWidget(output_group)

        # === BARRA DE PROGRESO ===
        # Título de la barra de progreso
        progress_title = QLabel("📊 Progreso de la operación")
        progress_title.setStyleSheet("""
            font-size: 11px;
            font-weight: bold;
            color: #134e4a;
            margin-top: 5px;
        """)
        main_layout.addWidget(progress_title)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(24)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                text-align: center;
                background-color: #f8fafc;
                font-size: 10px;
                font-weight: bold;
                color: #134e4a;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                                 stop:0 #0d9488, stop:1 #2dd4bf);
                border-radius: 5px;
            }
        """)
        main_layout.addWidget(self.progress_bar)

        # Label de estado 
        self.estado_label = QLabel("✅ Listo para iniciar")
        self.estado_label.setWordWrap(True)
        self.estado_label.setStyleSheet("""
            QLabel {
                background-color: #f0fdfa;
                border: 1px solid #99f6e4;
                border-radius: 6px;
                padding: 8px;
                font-size: 10px;
                color: #134e4a;
                margin-top: 5px;
            }
        """)
        main_layout.addWidget(self.estado_label)

        # === BOTONES DE ACCIÓN ===
        action_layout = QHBoxLayout()
        action_layout.setSpacing(10)

        self.btn_unir = QPushButton("🚀 UNIR CAPAS")
        self.btn_unir.setEnabled(False)
        self.btn_unir.setFixedHeight(40)
        self.btn_unir.setStyleSheet("""
            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                                 stop:0 #0d9488, stop:1 #14b8a6);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                                 stop:0 #0f766e, stop:1 #0d9488);
            }
            QPushButton:disabled { background-color: #cbd5e1; }
        """)
        self.btn_unir.clicked.connect(self.unir_capas)

        self.btn_cancelar = QPushButton("✖ CERRAR")
        self.btn_cancelar.setFixedHeight(40)
        self.btn_cancelar.setFixedWidth(120)
        self.btn_cancelar.setStyleSheet("""
            QPushButton {
                background-color: #e76f51;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #d45a3a; }
        """)
        self.btn_cancelar.clicked.connect(self.reject)

        action_layout.addStretch()
        action_layout.addWidget(self.btn_unir)
        action_layout.addWidget(self.btn_cancelar)
        action_layout.addStretch()

        main_layout.addLayout(action_layout)

        # === CRÉDITOS ===
        credit_layout = QHBoxLayout()
        credit_layout.setContentsMargins(5, 8, 5, 3)

        heart_icon = QLabel("❤️")
        heart_icon.setStyleSheet("font-size: 9px; color: #e76f51;")
        credit_layout.addWidget(heart_icon)

        credit_label = QLabel("Desarrollado por Raúl Víquez | viquezr@gmail.com")
        credit_label.setStyleSheet("""
            color: #64748b;
            font-size: 9px;
            font-style: italic;
        """)
        credit_label.setAlignment(Qt.AlignCenter)
        credit_layout.addWidget(credit_label)

        credit_layout.addStretch()
        main_layout.addLayout(credit_layout)

        self.setLayout(main_layout)

        # Configuración de la ventana
        self.setWindowTitle("🔄 Unir Capas Vectoriales")
        self.setMinimumSize(600, 550)
        self.setFixedSize(650, 600)

        # Conectar señales
        self.lista_capas.itemChanged.connect(self.actualizar_contador)
        self.lista_capas.itemChanged.connect(self.validar_formulario)

        # Cargar capas
        QTimer.singleShot(100, self.actualizar_lista_capas)

    def crear_pagina_seleccion(self):
        """Página principal de selección"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        # Grupo Capas
        grupo_capas = QGroupBox("📋 CAPAS DISPONIBLES")
        layout_capas = QVBoxLayout()
        
        self.lista_capas = QListWidget()
        self.lista_capas.setMinimumHeight(250)
        self.lista_capas.setSelectionMode(QListWidget.NoSelection)
        layout_capas.addWidget(self.lista_capas)
        
        # Botones de acción
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        self.btn_agregar_todas = QPushButton("✓ SELECCIONAR TODAS")
        self.btn_agregar_todas.clicked.connect(self.agregar_todas_las_capas)
        
        self.btn_limpiar = QPushButton("✗ LIMPIAR TODO")
        self.btn_limpiar.clicked.connect(self.limpiar_seleccion)
        
        self.btn_refrescar = QPushButton("↻ REFRESCAR")
        self.btn_refrescar.clicked.connect(self.refrescar_lista_capas)
        
        self.contador_label = QLabel("0 seleccionadas")
        self.contador_label.setObjectName("contador_label")
        self.contador_label.setAlignment(Qt.AlignCenter)
        self.contador_label.setStyleSheet("color: #e94560; font-weight: bold; background: white; padding: 5px; border-radius: 5px;")
        
        btn_layout.addWidget(self.btn_agregar_todas)
        btn_layout.addWidget(self.btn_limpiar)
        btn_layout.addWidget(self.btn_refrescar)
        btn_layout.addStretch()
        btn_layout.addWidget(self.contador_label)
        
        layout_capas.addLayout(btn_layout)
        grupo_capas.setLayout(layout_capas)
        layout.addWidget(grupo_capas)

        # Grupo Opciones
        grupo_opciones = QGroupBox("⚙️ OPCIONES AVANZADAS")
        layout_opciones = QVBoxLayout()
        
        self.check_longitud_maxima = QCheckBox("✓ Usar longitud máxima de campos")
        self.check_longitud_maxima.setChecked(True)
        layout_opciones.addWidget(self.check_longitud_maxima)
        
        grupo_opciones.setLayout(layout_opciones)
        layout.addWidget(grupo_opciones)

        # Grupo Archivo Salida
        grupo_salida = QGroupBox("💾 ARCHIVO DE SALIDA")
        layout_salida = QVBoxLayout()
        
        ruta_layout = QHBoxLayout()
        ruta_layout.setSpacing(10)
        
        self.ruta_label = QLabel("📁 Ningún archivo seleccionado")
        self.ruta_label.setObjectName("ruta_label")
        
        self.btn_examinar = QPushButton("📂 EXAMINAR")
        self.btn_examinar.setObjectName("btn_secundario")
        self.btn_examinar.setFixedWidth(120)
        self.btn_examinar.clicked.connect(self.seleccionar_archivo_salida)
        
        ruta_layout.addWidget(self.ruta_label, 1)
        ruta_layout.addWidget(self.btn_examinar)
        
        layout_salida.addLayout(ruta_layout)
        grupo_salida.setLayout(layout_salida)
        layout.addWidget(grupo_salida)

        # Botón Unir
        self.btn_unir = QPushButton("🚀 INICIAR UNIÓN")
        self.btn_unir.setObjectName("btn_exito")
        self.btn_unir.setEnabled(False)
        self.btn_unir.setMinimumHeight(45)
        self.btn_unir.clicked.connect(self.unir_capas)
        layout.addWidget(self.btn_unir)

        layout.addStretch()
        
        # Conectar señales
        self.lista_capas.itemChanged.connect(self.actualizar_contador)
        self.lista_capas.itemChanged.connect(self.validar_formulario)
        
        return page

    def crear_pagina_progreso(self):
        """Página de progreso"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(20)

        # Título de progreso
        self.progreso_title = QLabel("⚙️ PROCESANDO UNIÓN DE CAPAS")
        self.progreso_title.setAlignment(Qt.AlignCenter)
        self.progreso_title.setStyleSheet("font-size: 16px; font-weight: bold; color: white; padding: 10px; background: rgba(0,0,0,0.5); border-radius: 8px;")
        layout.addWidget(self.progreso_title)

        layout.addStretch()

        # Barra de progreso
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimumHeight(35)
        layout.addWidget(self.progress_bar)

        # Label de estado
        self.estado_label = QLabel("Preparando...")
        self.estado_label.setObjectName("status_label")
        self.estado_label.setWordWrap(True)
        self.estado_label.setMinimumHeight(80)
        layout.addWidget(self.estado_label)

        layout.addStretch()

        # Botón cancelar
        self.btn_cancelar_proceso = QPushButton("✖ CANCELAR PROCESO")
        self.btn_cancelar_proceso.setMinimumHeight(40)
        self.btn_cancelar_proceso.clicked.connect(self.cancelar_proceso)
        layout.addWidget(self.btn_cancelar_proceso)

        return page

    def actualizar_lista_capas(self):
        """Actualiza lista de capas"""
        self.lista_capas.clear()
        
        capas = [layer for layer in QgsProject.instance().mapLayers().values() 
                if isinstance(layer, QgsVectorLayer)]
        capas.sort(key=lambda x: x.name())
        
        iconos = {0: "📍 PUNTO", 1: "📏 LÍNEA", 2: "🔲 POLÍGONO"}
        
        for capa in capas:
            icono = iconos.get(capa.geometryType(), "❓ DESCONOCIDO")
            nombre = capa.name()
            features = capa.featureCount()
            
            texto = f"{icono}   {nombre}   [{features:,} características]"
            
            item = QListWidgetItem(texto)
            item.setData(Qt.UserRole, capa.id())
            item.setCheckState(Qt.Unchecked)
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            
            self.lista_capas.addItem(item)
        
        self.actualizar_contador()

    def refrescar_lista_capas(self):
        """Refresca manteniendo selección"""
        seleccionadas = self.obtener_capas_seleccionadas_ids()
        self.actualizar_lista_capas()
        
        for i in range(self.lista_capas.count()):
            item = self.lista_capas.item(i)
            if item.data(Qt.UserRole) in seleccionadas:
                item.setCheckState(Qt.Checked)

    def obtener_capas_seleccionadas_ids(self):
        """Obtiene IDs de capas seleccionadas"""
        seleccionadas = []
        for i in range(self.lista_capas.count()):
            item = self.lista_capas.item(i)
            if item.checkState() == Qt.Checked:
                seleccionadas.append(item.data(Qt.UserRole))
        return seleccionadas

    def agregar_todas_las_capas(self):
        """Selecciona todas"""
        for i in range(self.lista_capas.count()):
            self.lista_capas.item(i).setCheckState(Qt.Checked)

    def limpiar_seleccion(self):
        """Deselecciona todas"""
        for i in range(self.lista_capas.count()):
            self.lista_capas.item(i).setCheckState(Qt.Unchecked)

    def actualizar_contador(self):
        """Actualiza contador"""
        total = self.lista_capas.count()
        seleccionadas = len(self.obtener_capas_seleccionadas_ids())
        self.contador_label.setText(f"{seleccionadas} / {total} seleccionadas")

    def seleccionar_archivo_salida(self):
        """Selecciona archivo de salida"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Guardar capa unida", 
            os.path.expanduser("~/"),
            "Shapefile (*.shp);;GeoPackage (*.gpkg)"
        )
        
        if file_path:
            if not file_path.lower().endswith(('.shp', '.gpkg')):
                file_path += '.shp'
            
            self.output_path = file_path
            nombre = os.path.basename(file_path)
            self.ruta_label.setText(f"💾 {nombre}")
            self.validar_formulario()

    def obtener_capas_seleccionadas(self):
        """Obtiene capas seleccionadas"""
        capas = []
        for i in range(self.lista_capas.count()):
            item = self.lista_capas.item(i)
            if item.checkState() == Qt.Checked:
                capa = QgsProject.instance().mapLayer(item.data(Qt.UserRole))
                if capa and capa.isValid():
                    capas.append({'id': capa.id(), 'name': capa.name()})
        return capas

    def validar_formulario(self):
        """Valida formulario"""
        self.btn_unir.setEnabled(
            bool(self.obtener_capas_seleccionadas() and self.output_path)
        )

    def unir_capas(self):
        """Inicia unión"""
        self.capas_seleccionadas = self.obtener_capas_seleccionadas()
        
        if not self.capas_seleccionadas or not self.output_path:
            return
        
        # Verificar CRS
        crs_list = []
        crs_nombres = []
        for capa_info in self.capas_seleccionadas:
            capa = QgsProject.instance().mapLayer(capa_info['id'])
            if capa:
                crs = capa.crs()
                crs_list.append(crs.authid())
                crs_nombres.append(f"• {capa.name()}: {crs.authid()}")
        
        crs_unicos = set(crs_list)
        crs_destino = None
        
        if len(crs_unicos) > 1:
            mensaje = "⚠️ CRS DIFERENTES DETECTADOS\n\n"
            mensaje += "Las capas tienen diferentes sistemas de coordenadas:\n"
            mensaje += "\n".join(crs_nombres[:5])
            if len(crs_nombres) > 5:
                mensaje += f"\n• ... y {len(crs_nombres)-5} más\n"
            
            mensaje += "\n\n¿Qué CRS quieres usar para la capa de salida?\n"
            mensaje += "• EPSG:32617 (WGS 84 / UTM zone 17N)\n"
            mensaje += "• Usar el CRS de la primera capa\n"
            mensaje += "• Cancelar"
            
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("🔄 Seleccionar CRS destino")
            msg_box.setText(mensaje)
            msg_box.setIcon(QMessageBox.Question)
            
            btn_utm = msg_box.addButton("EPSG:32617", QMessageBox.YesRole)
            btn_primer = msg_box.addButton("Primer CRS", QMessageBox.NoRole)
            btn_cancel = msg_box.addButton("Cancelar", QMessageBox.RejectRole)
            
            msg_box.exec_()
            
            if msg_box.clickedButton() == btn_cancel:
                return
            elif msg_box.clickedButton() == btn_utm:
                crs_destino = QgsCoordinateReferenceSystem("EPSG:32617")
                if not crs_destino.isValid():
                    QMessageBox.warning(self, "Error", "EPSG:32617 no es válido")
                    return
            else:
                primera_capa = QgsProject.instance().mapLayer(self.capas_seleccionadas[0]['id'])
                crs_destino = primera_capa.crs()
        else:
            primera_capa = QgsProject.instance().mapLayer(self.capas_seleccionadas[0]['id'])
            crs_destino = primera_capa.crs()

        # Cambiar a página de progreso

        self.progress_bar.setValue(0)
        self.estado_label.setText("🚀 Iniciando proceso de unión...")

        
        # Iniciar thread
        self.thread = UnirCapasThread(
            self.capas_seleccionadas, 
            self.output_path,
            self.check_longitud_maxima.isChecked(),
            crs_destino
        )
        self.thread.progress_updated.connect(self.actualizar_progreso)
        self.thread.finished_process.connect(self.proceso_finalizado)
        self.thread.start()

    

    def actualizar_progreso(self, valor, mensaje):
        """Actualiza UI"""
        self.progress_bar.setValue(valor)
        self.estado_label.setText(mensaje)

    
    def proceso_finalizado(self, exito, mensaje, estadisticas):
        """Finalización del proceso"""
        # Restaurar controles
        self.btn_unir.setEnabled(True)
        self.btn_examinar.setEnabled(True)
        self.btn_agregar_todas.setEnabled(True)
        self.btn_limpiar.setEnabled(True)
        self.btn_refrescar.setEnabled(True)
        self.check_longitud_maxima.setEnabled(True)
        self.lista_capas.setEnabled(True)

        if exito:
            self.progress_bar.setValue(100)
            self.estado_label.setText("✅ Proceso completado con éxito")
            QMessageBox.information(self, "✅ Éxito", mensaje)
        else:
            self.progress_bar.setValue(0)
            self.estado_label.setText(f"❌ Error: {mensaje[:100]}")
            QMessageBox.critical(self, "❌ Error", mensaje)

        self.thread = None
        
# ============================================================================
# CLASE PRINCIPAL DEL PLUGIN
# ============================================================================

class UnirCapasPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.plugin_dir = os.path.dirname(__file__)

    def initGui(self):
        """Inicializa la interfaz del plugin"""
        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        if os.path.exists(icon_path):
            self.action = QAction(QIcon(icon_path), "Unir Capas", self.iface.mainWindow())
        else:
            self.action = QAction("🔄 Unir Capas", self.iface.mainWindow())
        
        self.action.setObjectName("unirCapas")
        self.action.triggered.connect(self.run)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("&Unir Capas", self.action)

    def unload(self):
        """Descarga el plugin"""
        self.iface.removePluginMenu("&Unir Capas", self.action)
        self.iface.removeToolBarIcon(self.action)

    def run(self):
        """Ejecuta el plugin"""
        dialog = UnirCapasDialog(self.iface.mainWindow())
        dialog.exec_()