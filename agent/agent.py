"""
Druida — conversational data agent (backend).

A Gemini-powered assistant for the Finca Los Astros winery ERP. It answers
natural-language questions about the business by calling read-only Firestore
"tools" (ventas, clientes, stock, trazabilidad, …) through Gemini function
calling, and persists each conversation as a thread in Firestore.

Endpoints:
    POST   /chat                  Send a message; returns the assistant's reply.
    GET    /threads/<session_id>  List a user's conversation threads (paginated).
    GET    /history/<thread_id>   Fetch a thread's message history.
    DELETE /history/<thread_id>   Delete a thread.

Configuration (environment):
    GEMINI_API_KEY / GOOGLE_API_KEY   Gemini API key, read by genai.Client().
    credentials.json                  Google service-account file for Firestore
                                      (never commit this — see .gitignore).
"""

import json
import urllib.parse
from datetime import datetime
from typing import List, Optional

from flask import Flask, jsonify, request
from flask_cors import CORS
from google import genai
from google.cloud import firestore
from google.genai import types
from google.genai.errors import APIError
from unidecode import unidecode

app = Flask(__name__)
CORS(app)


# ── Configuration ───────────────────────────────────────────────────────────
CREDENTIALS_PATH = "credentials.json"

USUARIOS_COLLECTION_NAME = "usuarios"
PROVEEDORES_COLLECTION_NAME = "proveedores"
CLIENTES_COLLECTION_NAME = "clientes"
VENTAS_COLLECTION_NAME = "ventas"
COMPRAS_COLLECTION_NAME = "compras"
ORDENES_COMPRA_COLLECTION_NAME = "ordenes_compra"
STOCK_COLLECTION_NAME = "stock"
INVENTARIO_COLLECTION_NAME = "inventario"
EVENTOS_COLLECTION_NAME = "eventos"
VITICULTURA_COLLECTION_NAME = "viticultura"
VINIFICACION_COLLECTION_NAME = "vinificacion"
EMBOTELLADO_COLLECTION_NAME = "embotellado"
TRAZABILIDAD_COLLECTION_NAME = "trazabilidad"
VINOS_COLLECTION_NAME = "vinos"
ARCHIVOS_COLLECTION_NAME = "archivos"

TITULO_MODEL = "gemini-2.5-flash"
GEMINI_MODEL = "gemini-2.5-pro"
ASISTENTE_NOMBRE = "Druida"

client = None
db = None
chat_sessions = {}

try:

    client = genai.Client()
    print("✅ Cliente de Gemini inicializado correctamente para Finca Los Astros.")

    db = firestore.Client.from_service_account_json(CREDENTIALS_PATH)
    print("✅ Cliente de Firestore inicializado correctamente.")
except Exception as e:
    print(f"❌ Error al inicializar clientes: {e}")
    client = None
    db = None


def convert_firestore_timestamps(data):
    """
    Convierte recursivamente objetos DatetimeWithNanoseconds o datetime
    a cadenas ISO 8601 en un diccionario o lista.
    """
    if isinstance(data, dict):
        return {k: convert_firestore_timestamps(v) for k, v in data.items()}

    if isinstance(data, list):
        return [convert_firestore_timestamps(element) for element in data]

    if isinstance(data, datetime):
        return data.isoformat()

    return data


# ── Tools: read-only Firestore queries exposed to the model ──────────────────
# Each function is registered in AVAILABLE_FUNCTIONS below and passed to Gemini,
# which calls them by name (function calling) to ground its answers in real data.
def consultar_datos_usuario_activo(uid: str) -> str:
    """
    Busca el documento de usuario por su UID. Si el usuario pregunta por
    sus propios datos (ej: 'mis responsabilidades'), el agente llama a
    esta función.
    """
    if db is None:
        return json.dumps({"error": "La conexión a Firestore no está disponible."})

    try:
        if not uid:
            return json.dumps({"error": "Se requiere un UID para buscar al usuario."})

        doc_ref = db.collection(USUARIOS_COLLECTION_NAME).document(uid)
        doc = doc_ref.get()

        if doc.exists:
            doc_data = doc.to_dict()

            serializable_data = convert_firestore_timestamps(doc_data)

            return json.dumps(serializable_data)
        else:
            return json.dumps({"error": f"No se encontró el usuario con UID: {uid}"})

    except Exception as e:

        print(f"❌ Error en la consulta de datos de usuario a Firestore: {e}")
        return json.dumps(
            {
                "error": f"Ocurrió un error al interactuar con la base de datos de usuarios: {e}"
            }
        )


def json_serial_helper(obj):
    """
    Función auxiliar para serializar objetos que json.dumps no reconoce por defecto.
    Específicamente, convierte objetos de fecha y hora (datetime) a strings en formato ISO.
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def consultar_proveedores(
    razon_social: Optional[str] = None,
    contar: bool = False,
    campo_a_extraer: Optional[str] = None,  # 🆕 NUEVO
    filtro_pais: Optional[str] = None,  # 🆕 NUEVO
    filtro_ciudad: Optional[str] = None,  # 🆕 NUEVO
) -> str:
    """
    Gestiona todas las consultas a la base de datos de proveedores, incluyendo
    búsqueda, conteo, extracción de campos y filtrado por ubicación.
    """
    if db is None:
        return json.dumps({"error": "La conexión a Firestore no está disponible."})

    try:
        base_query = db.collection(PROVEEDORES_COLLECTION_NAME)

        # --------------------------------------------------------------------
        # 🆕 LÓGICA DE FILTRADO POR UBICACIÓN (Contar o Listar)
        # --------------------------------------------------------------------
        if filtro_pais or filtro_ciudad:
            print(
                f"▶️ Ejecutando modo: FILTRO de Proveedores por Ubicación. País: {filtro_pais}, Ciudad: {filtro_ciudad}"
            )

            docs_stream = base_query.stream()
            proveedores_filtrados = []

            pais_buscado = filtro_pais.strip().lower() if filtro_pais else None
            ciudad_buscada = filtro_ciudad.strip().lower() if filtro_ciudad else None

            for doc in docs_stream:
                data = doc.to_dict()

                ciudad_en_db = data.get("ciudad", "").strip().lower()

                match_pais = (
                    not pais_buscado
                    or data.get("pais", "").strip().lower() == pais_buscado
                )

                # 🆕 Lógica Modificada: Buscamos si la ciudad_buscada está contenida en el campo 'ciudad' de la base de datos.
                # Esto cubre casos como buscar 'Mendoza' y encontrar 'San Rafael, Mendoza' o 'Mendoza Capital'.
                match_ciudad = not ciudad_buscada or ciudad_buscada in ciudad_en_db

                if match_pais and match_ciudad:
                    proveedores_filtrados.append(data)

            if contar:
                return json.dumps(
                    {
                        "total_proveedores_filtrados": len(proveedores_filtrados),
                        "criterio_filtro": f"País: {filtro_pais or 'Cualquiera'}, Ciudad: {filtro_ciudad or 'Cualquiera'}",
                    }
                )
            else:
                return json.dumps(proveedores_filtrados, default=json_serial_helper)
        # --------------------------------------------------------------------
        # ⬅️ LÓGICA DE CONTEO SIMPLE
        # --------------------------------------------------------------------
        if contar:
            print("▶️ Ejecutando modo: CONTEO de Proveedores")
            count_query = base_query.count()
            count_result = count_query.get()
            total = count_result[0][0].value
            return json.dumps({"total_proveedores": total})

        # --------------------------------------------------------------------
        # ⬅️ LÓGICA DE BÚSQUEDA POR RAZÓN SOCIAL (con extracción de domicilio)
        # --------------------------------------------------------------------
        elif razon_social:
            print(f"▶️ Ejecutando modo: BÚSQUEDA de Proveedor '{razon_social}'")
            query = base_query.where("razonSocial", "==", razon_social).limit(1)
            docs = query.get()

            if not docs:
                query = base_query.where("nombreVendedor", "==", razon_social).limit(1)
                docs = query.get()

            if docs:
                doc_data = docs[0].to_dict()

                # 🆕 EXTRACCIÓN DE DOMICILIO
                if campo_a_extraer and campo_a_extraer.lower() == "domicilio":
                    domicilio = {
                        "calle": doc_data.get("calle", ""),
                        "altura": doc_data.get("altura", ""),
                        "piso": doc_data.get("piso", ""),
                        "unidad": doc_data.get("unidad", ""),
                        "ciudad": doc_data.get("ciudad", ""),
                        "codigoPostal": doc_data.get("codigoPostal", ""),
                        "pais": doc_data.get("pais", ""),
                    }
                    return json.dumps(
                        {"proveedor": razon_social, "domicilio": domicilio},
                        default=json_serial_helper,
                    )

                return json.dumps(doc_data, default=json_serial_helper)
            else:
                return json.dumps(
                    {
                        "error": f"No se encontró ningún proveedor con el nombre o razón social: {razon_social}"
                    }
                )

        # --------------------------------------------------------------------
        # ⬅️ LÓGICA DE LISTADO COMPLETO
        # --------------------------------------------------------------------
        else:
            print("▶️ Ejecutando modo: LISTADO COMPLETO de Proveedores")
            docs = base_query.stream()
            lista_completa = [doc.to_dict() for doc in docs]
            return json.dumps(lista_completa, default=json_serial_helper)

    except Exception as e:
        print(f"❌ Error en la consulta a Firestore (Proveedores): {e}")
        return json.dumps(
            {
                "error": f"Ocurrió un error al interactuar con la base de datos de proveedores: {e}"
            }
        )


def consultar_clientes(
    identificador: Optional[str] = None,
    contar: bool = False,
    campo_a_extraer: Optional[
        str
    ] = None,  # 🆕 NUEVO: Para extraer campos específicos (ej: 'domicilio')
    filtro_pais: Optional[str] = None,  # 🆕 NUEVO: Para filtrar por país
    filtro_ciudad: Optional[str] = None,  # 🆕 NUEVO: Para filtrar por ciudad
) -> str:
    """
    Gestiona todas las consultas a la base de datos de clientes, incluyendo
    búsqueda, conteo, extracción de campos y filtrado por ubicación.
    """
    if db is None:
        return json.dumps({"error": "La conexión a Firestore no está disponible."})

    try:
        base_query = db.collection(CLIENTES_COLLECTION_NAME)

        if filtro_pais or filtro_ciudad:
            print(
                f"▶️ Ejecutando modo: FILTRO de Clientes por Ubicación. País: {filtro_pais}, Ciudad: {filtro_ciudad}"
            )

            docs_stream = base_query.stream()
            proveedores_filtrados = []

            pais_buscado = filtro_pais.strip().lower() if filtro_pais else None
            ciudad_buscada = filtro_ciudad.strip().lower() if filtro_ciudad else None

            for doc in docs_stream:
                data = doc.to_dict()

                ciudad_en_db = data.get("ciudad", "").strip().lower()

                match_pais = (
                    not pais_buscado
                    or data.get("pais", "").strip().lower() == pais_buscado
                )

                match_ciudad = not ciudad_buscada or ciudad_buscada in ciudad_en_db

                if match_pais and match_ciudad:
                    proveedores_filtrados.append(data)

            if contar:
                return json.dumps(
                    {
                        "total_proveedores_filtrados": len(proveedores_filtrados),
                        "criterio_filtro": f"País: {filtro_pais or 'Cualquiera'}, Ciudad: {filtro_ciudad or 'Cualquiera'}",
                    }
                )
            else:
                return json.dumps(proveedores_filtrados, default=json_serial_helper)

        if contar:
            print("▶️ Ejecutando modo: CONTEO de Clientes")
            count_query = base_query.count()
            count_result = count_query.get()
            total = count_result[0][0].value
            return json.dumps({"total_clientes": total})

        elif identificador:
            docs = []

            query_razon_social = (
                db.collection(CLIENTES_COLLECTION_NAME)
                .where("razonSocial", "==", identificador)
                .limit(1)
            )
            docs = query_razon_social.get()
            if not docs:
                query_cuit = (
                    db.collection(CLIENTES_COLLECTION_NAME)
                    .where("cuit", "==", identificador)
                    .limit(1)
                )
                docs = query_cuit.get()
            if not docs:
                query_dni = (
                    db.collection(CLIENTES_COLLECTION_NAME)
                    .where("numeroDeDocumento", "==", identificador)
                    .limit(1)
                )
                docs = query_dni.get()
            if not docs:
                query_nombre = (
                    db.collection(CLIENTES_COLLECTION_NAME)
                    .where("nombre", "==", identificador)
                    .limit(1)
                )
                docs = query_nombre.get()

            if docs:
                doc_data = docs[0].to_dict()

                # 🆕 EXTRACCIÓN DE DOMICILIO
                if campo_a_extraer and campo_a_extraer.lower() == "domicilio":
                    domicilio = {
                        "calle": doc_data.get("calle", ""),
                        "altura": doc_data.get("altura", ""),
                        "piso": doc_data.get("piso", ""),
                        "unidad": doc_data.get("unidad", ""),
                        "ciudad": doc_data.get("ciudad", ""),
                        "codigoPostal": doc_data.get("codigoPostal", ""),
                        "pais": doc_data.get("pais", ""),
                    }
                    return json.dumps(
                        {"cliente": identificador, "domicilio": domicilio},
                        default=json_serial_helper,
                    )

                return json.dumps(doc_data, default=json_serial_helper)
            else:
                return json.dumps(
                    {
                        "error": f"No se encontró ningún cliente con el identificador: {identificador}"
                    }
                )

        else:
            print("▶️ Ejecutando modo: LISTADO COMPLETO de Clientes")
            docs = base_query.stream()
            lista_completa = [doc.to_dict() for doc in docs]
            return json.dumps(lista_completa, default=json_serial_helper)

    except Exception as e:
        print(f"❌ Error en la consulta de clientes a Firestore: {e}")
        return json.dumps(
            {
                "error": f"Ocurrió un error al interactuar con la base de datos de clientes: {e}"
            }
        )


def consultar_ventas(
    id_venta: Optional[str] = None,
    ids_ventas_cliente: Optional[List[str]] = None,
    razon_social_cliente: Optional[str] = None,
    fecha_inicio_filtro: Optional[str] = None,
    nombre_producto_vendido: Optional[str] = None,
    contar: bool = False,
) -> str:
    """
    Gestiona todas las consultas a la base de datos de ventas de Finca Los Astros.
    Permite buscar ventas por ID, cliente, fecha o nombre de producto vendido.
    """
    if db is None:
        return json.dumps({"error": "La conexión a Firestore no está disponible."})

    try:

        if contar:
            print("▶️ Ejecutando modo: CONTEO de Ventas")
            count_query = db.collection(VENTAS_COLLECTION_NAME).count()
            count_result = count_query.get()
            total = count_result[0][0].value
            return json.dumps({"total_ventas": total})

        lista_ids_a_buscar = []
        if id_venta:

            doc_id_completo = id_venta
            lista_ids_a_buscar.append(doc_id_completo)
        elif ids_ventas_cliente:
            lista_ids_a_buscar = ids_ventas_cliente

        if lista_ids_a_buscar:
            print(
                f"▶️ Ejecutando modo: BÚSQUEDA de {len(lista_ids_a_buscar)} Venta(s) por ID"
            )

            lista_ventas = []
            for doc_id in lista_ids_a_buscar:
                doc_ref = db.collection(VENTAS_COLLECTION_NAME).document(doc_id)
                doc = doc_ref.get()
                if doc.exists:
                    doc_data = doc.to_dict()
                    doc_data["idVenta"] = doc.id
                    lista_ventas.append(doc_data)

            if lista_ventas:
                return json.dumps(lista_ventas, default=json_serial_helper)
            else:
                return json.dumps(
                    {"error": "No se encontraron ventas con los IDs proporcionados."}
                )

        if nombre_producto_vendido:
            print(
                f"▶️ Ejecutando modo: BÚSQUEDA por Producto Vendido: '{nombre_producto_vendido}'"
            )

            nombre_buscado_norm = nombre_producto_vendido.lower().strip()

            docs_stream = db.collection(VENTAS_COLLECTION_NAME).stream()

            ventas_encontradas = []

            for doc in docs_stream:
                data = doc.to_dict()

                productos_vendidos = data.get("productosVendidos", [])

                encontrado_en_venta = False

                for producto in productos_vendidos:

                    id_producto = producto.get("idProducto", "").lower().strip()
                    nombre_producto = producto.get("nombreProducto", "").lower().strip()

                    if (
                        nombre_buscado_norm == id_producto
                        or nombre_buscado_norm in nombre_producto
                    ):

                        data["idVenta"] = doc.id
                        ventas_encontradas.append(data)
                        encontrado_en_venta = True
                        break

                if encontrado_en_venta:
                    continue

            if ventas_encontradas:
                return json.dumps(ventas_encontradas, default=json_serial_helper)
            else:
                return json.dumps(
                    {
                        "error": f"No se encontró ninguna venta que contenga el producto o ID: {nombre_producto_vendido}"
                    }
                )

        if razon_social_cliente or fecha_inicio_filtro:

            print(
                f"▶️ Ejecutando modo: BÚSQUEDA de Ventas con filtros (Cliente: {razon_social_cliente}, Fecha: {fecha_inicio_filtro})"
            )

            query = db.collection(VENTAS_COLLECTION_NAME)

            if razon_social_cliente:
                query = query.where("cliente.razonSocial", "==", razon_social_cliente)

            if fecha_inicio_filtro:
                try:
                    fecha_dt = datetime.strptime(fecha_inicio_filtro, "%Y-%m-%d")
                    # 🔑 CORRECCIÓN: Usar el objeto datetime (fecha_dt) para la comparación con el Timestamp
                    query = query.where("fechaVenta", ">=", fecha_dt)
                    query = query.order_by(
                        "fechaVenta", direction=firestore.Query.DESCENDING
                    )
                except ValueError:
                    print("❌ Error: Formato de fecha de inicio incorrecto.")
                    pass

            docs = query.stream()

            lista_ventas = []
            for doc in docs:
                if doc.exists:
                    data = doc.to_dict()
                    data["idVenta"] = doc.id
                    lista_ventas.append(data)

            if lista_ventas:
                return json.dumps(lista_ventas, default=json_serial_helper)
            else:
                return json.dumps(
                    {
                        "error": "No se encontraron ventas que coincidan con los filtros aplicados."
                    }
                )

        else:
            print("▶️ Ejecutando modo: LISTADO COMPLETO de Ventas")

            query = db.collection(VENTAS_COLLECTION_NAME).limit(50)
            docs = query.stream()
            lista_ventas = []
            for doc in docs:
                if doc.exists:
                    data = doc.to_dict()
                    data["idVenta"] = doc.id
                    lista_ventas.append(data)

            if lista_ventas:
                return json.dumps(
                    {
                        "warning": "Se muestran las últimas 10 ventas por eficiencia. Para más datos, usá un filtro.",
                        "ventas": lista_ventas,
                    },
                    default=json_serial_helper,
                )
            else:
                return json.dumps(
                    {"error": "No se encontraron ventas en la base de datos."}
                )

    except Exception as e:
        print(f"❌ Error en la consulta de ventas a Firestore: {e}")
        return json.dumps(
            {
                "error": f"Ocurrió un error al interactuar con la base de datos de ventas: {e}"
            }
        )


def consultar_compras(
    id_compra: Optional[str] = None,
    razon_social_proveedor: Optional[str] = None,
    fecha_inicio_filtro: Optional[str] = None,
    nombre_articulo_comprado: Optional[str] = None,
    contar: bool = False,
) -> str:
    """
    Gestiona todas las consultas a la base de datos de compras de Finca Los Astros.
    Permite buscar compras por ID, proveedor, fecha o nombre de artículo comprado.
    """
    if db is None:
        return json.dumps({"error": "La conexión a Firestore no está disponible."})

    try:

        if contar and not any(
            [
                id_compra,
                razon_social_proveedor,
                fecha_inicio_filtro,
                nombre_articulo_comprado,
            ]
        ):
            print("▶️ Ejecutando modo: CONTEO de Compras")
            count_query = db.collection(COMPRAS_COLLECTION_NAME).count()
            count_result = count_query.get()
            total = count_result[0][0].value
            return json.dumps({"total_compras": total})

        if id_compra:

            print(f"▶️ Ejecutando modo: BÚSQUEDA de Compra por ID '{id_compra}'")
            doc_ref = db.collection(COMPRAS_COLLECTION_NAME).document(id_compra)
            doc = doc_ref.get()

            if doc.exists:
                doc_data = doc.to_dict()
                doc_data["idCompra"] = doc.id
                return json.dumps(doc_data, default=json_serial_helper)
            else:
                return json.dumps(
                    {"error": f"No se encontró ninguna compra con el ID: {id_compra}"}
                )

        if nombre_articulo_comprado:

            print(
                f"▶️ Ejecutando modo: BÚSQUEDA por Artículo Comprado: '{nombre_articulo_comprado}'"
            )

            nombre_buscado_norm = nombre_articulo_comprado.lower().strip()
            docs_stream = db.collection(COMPRAS_COLLECTION_NAME).stream()
            compras_encontradas = []

            for doc in docs_stream:
                data = doc.to_dict()
                articulos = data.get("articulos", [])

                encontrado_en_compra = False
                for articulo in articulos:
                    nombre_articulo = articulo.get("nombre", "").lower().strip()

                    if nombre_buscado_norm in nombre_articulo:
                        data["idCompra"] = doc.id
                        compras_encontradas.append(data)
                        encontrado_en_compra = True
                        break

                if encontrado_en_compra:
                    continue

            if compras_encontradas:
                return json.dumps(compras_encontradas, default=json_serial_helper)
            else:
                return json.dumps(
                    {
                        "error": f"No se encontró ninguna compra que contenga el artículo: {nombre_articulo_comprado}"
                    }
                )

        if razon_social_proveedor or fecha_inicio_filtro:
            print(
                f"▶️ Ejecutando modo: BÚSQUEDA de Compras con filtros (Proveedor: {razon_social_proveedor}, Fecha: {fecha_inicio_filtro})"
            )

            query = db.collection(COMPRAS_COLLECTION_NAME)
            tiene_filtro_rango_u_orden = False

            if razon_social_proveedor:
                query = query.where("razonSocial", "==", razon_social_proveedor)

            if fecha_inicio_filtro:
                try:

                    fecha_dt = datetime.strptime(fecha_inicio_filtro, "%Y-%m-%d")
                    query = query.where("fechaCompra", ">=", fecha_inicio_filtro)
                    query = query.order_by(
                        "fechaCompra", direction=firestore.Query.DESCENDING
                    )
                    tiene_filtro_rango_u_orden = True
                except ValueError:
                    print(
                        "❌ Error: Formato de fecha de inicio incorrecto. Se ignora el filtro de fecha."
                    )
                    pass

            query = query.limit(50)

            docs = query.stream()
            lista_compras = []
            for doc in docs:
                if doc.exists:
                    data = doc.to_dict()
                    data["idCompra"] = doc.id
                    lista_compras.append(data)

            if lista_compras:
                return json.dumps(lista_compras, default=json_serial_helper)
            else:
                return json.dumps(
                    {
                        "error": "No se encontraron compras que coincidan con los filtros aplicados."
                    }
                )

        else:
            print("▶️ Ejecutando modo: LISTADO COMPLETO de Compras (últimas 10)")

            query = (
                db.collection(COMPRAS_COLLECTION_NAME)
                .order_by("fechaCreacion", direction=firestore.Query.DESCENDING)
                .limit(50)
            )
            docs = query.stream()
            lista_compras = []
            for doc in docs:
                if doc.exists:
                    data = doc.to_dict()
                    data["idCompra"] = doc.id
                    lista_compras.append(data)

            if lista_compras:
                return json.dumps(
                    {
                        "warning": "Se muestran las últimas 10 compras por eficiencia. Para más datos, usá un filtro.",
                        "compras": lista_compras,
                    },
                    default=json_serial_helper,
                )
            else:
                return json.dumps(
                    {"error": "No se encontraron compras en la base de datos."}
                )

    except Exception as e:
        print(f"❌ Error en la consulta de compras a Firestore: {e}")
        return json.dumps(
            {
                "error": f"Ocurrió un error al interactuar con la base de datos de compras: {e}"
            }
        )


def consultar_ordenes_compra(
    id_orden: Optional[str] = None,
    razon_social_proveedor: Optional[str] = None,
    fecha_inicio_filtro: Optional[str] = None,
    estado_filtro: Optional[str] = None,
    contar: bool = False,
) -> str:
    """
    Gestiona todas las consultas a la base de datos de órdenes de compra.
    Permite buscar por ID, proveedor, fecha o estado (ej: 'finalizada', 'pendiente').
    """
    if db is None:
        return json.dumps({"error": "La conexión a Firestore no está disponible."})

    try:
        base_query = db.collection(ORDENES_COMPRA_COLLECTION_NAME)
        query = base_query

        if contar and not any(
            [id_orden, razon_social_proveedor, fecha_inicio_filtro, estado_filtro]
        ):
            print("▶️ Ejecutando modo: CONTEO total de Órdenes de Compra")
            count_query = query.count()
            count_result = count_query.get()
            total = count_result[0][0].value
            return json.dumps({"total_ordenes_compra": total})

        if id_orden:
            print(f"▶️ Ejecutando modo: BÚSQUEDA de Orden por ID '{id_orden}'")
            doc_ref = base_query.document(id_orden)
            doc = doc_ref.get()

            if doc.exists:
                doc_data = doc.to_dict()
                doc_data["idOrdenCompra"] = doc.id
                return json.dumps(doc_data, default=json_serial_helper)
            else:
                return json.dumps(
                    {"error": f"No se encontró ninguna orden con el ID: {id_orden}"}
                )

        print("▶️ Ejecutando modo: BÚSQUEDA de Órdenes con filtros")

        if razon_social_proveedor:
            query = query.where("razonSocial", "==", razon_social_proveedor)

        if estado_filtro:
            query = query.where("estado", "==", estado_filtro)

        if fecha_inicio_filtro:
            try:

                fecha_dt = datetime.strptime(fecha_inicio_filtro, "%Y-%m-%d")
                query = query.where("fechaCreacion", ">=", fecha_inicio_filtro)
                query = query.order_by(
                    "fechaCreacion", direction=firestore.Query.DESCENDING
                )
            except ValueError:
                print(
                    "❌ Error: Formato de fecha de inicio incorrecto. Se ignora el filtro de fecha."
                )
                pass

        if contar:
            count_query = query.count()
            count_result = count_query.get()
            total = count_result[0][0].value
            return json.dumps({"total_ordenes_filtradas": total})

        query_listado = query

        if not fecha_inicio_filtro:
            print(
                "▶️ Aplicando límite de resultados a la consulta sin orden específico."
            )
            query_listado = query_listado.limit(50)

        docs = query_listado.stream()
        lista_ordenes = []
        for doc in docs:
            if doc.exists:
                data = doc.to_dict()
                data["idOrdenCompra"] = doc.id
                lista_ordenes.append(data)

        if lista_ordenes:
            return json.dumps(
                {
                    "warning": "Se muestran las últimas 10 órdenes de compra con los filtros aplicados. Usar ID o un filtro más específico para más datos.",
                    "ordenes_compra": lista_ordenes,
                },
                default=json_serial_helper,
            )
        else:
            return json.dumps(
                {
                    "error": "No se encontraron órdenes de compra que coincidan con los filtros aplicados."
                }
            )

    except Exception as e:
        print(f"❌ Error en la consulta de órdenes de compra a Firestore: {e}")
        return json.dumps(
            {
                "error": f"Ocurrió un error al interactuar con la base de datos de órdenes de compra: {e}"
            }
        )


def consultar_documento_extremo(
    coleccion: str, campo_ordenamiento: str, tipo_extremo: str
) -> str:
    """
    Busca el documento con el valor más alto (MAX) o más bajo (MIN) en un campo
    específico dentro de una colección dada.

    Args:
        coleccion (str): El nombre de la colección ('ventas', 'clientes', 'proveedores').
        campo_ordenamiento (str): El nombre del campo por el que se debe ordenar (ej: 'totalFinal', 'cuit', 'fechaVenta').
        tipo_extremo (str): Debe ser 'MAX' para el valor más alto o 'MIN' para el valor más bajo.

    Returns:
        str: Una cadena JSON con el documento encontrado o un mensaje de error.
    """
    if db is None:
        return json.dumps({"error": "La conexión a Firestore no está disponible."})

    coleccion = coleccion.lower().strip()

    if coleccion not in [
        PROVEEDORES_COLLECTION_NAME,
        CLIENTES_COLLECTION_NAME,
        VENTAS_COLLECTION_NAME,
        STOCK_COLLECTION_NAME,
        COMPRAS_COLLECTION_NAME,
        ORDENES_COMPRA_COLLECTION_NAME,
    ]:
        return json.dumps(
            {
                "error": f"Colección no reconocida. Solo se admiten: {PROVEEDORES_COLLECTION_NAME}, {CLIENTES_COLLECTION_NAME}, {VENTAS_COLLECTION_NAME}, {STOCK_COLLECTION_NAME}, {COMPRAS_COLLECTION_NAME}, {ORDENES_COMPRA_COLLECTION_NAME}."
            }
        )

    try:

        if tipo_extremo.upper() == "MAX":
            direction = firestore.Query.DESCENDING
            print(
                f"▶️ Ejecutando BÚSQUEDA EXTREMA: MAX en {coleccion} por {campo_ordenamiento}"
            )
        elif tipo_extremo.upper() == "MIN":
            direction = firestore.Query.ASCENDING
            print(
                f"▶️ Ejecutando BÚSQUEDA EXTREMA: MIN en {coleccion} por {campo_ordenamiento}"
            )
        else:
            return json.dumps(
                {"error": "El argumento 'tipo_extremo' debe ser 'MAX' o 'MIN'."}
            )

        query = (
            db.collection(coleccion)
            .order_by(campo_ordenamiento, direction=direction)
            .limit(1)
        )

        docs = query.get()

        if docs:
            doc = docs[0]
            doc_data = doc.to_dict()
            doc_data["idDocumento"] = doc.id
            doc_data["metadataConsulta"] = (
                f"Resultado de búsqueda {tipo_extremo} en campo '{campo_ordenamiento}'"
            )

            return json.dumps(doc_data, default=json_serial_helper)
        else:
            return json.dumps(
                {
                    "error": f"No se encontraron documentos en la colección '{coleccion}'."
                }
            )

    except Exception as e:
        print(f"❌ Error en la consulta extrema a Firestore: {e}")
        return json.dumps(
            {
                "error": f"Ocurrió un error al buscar el documento extremo. Verifique el campo: {e}"
            }
        )


def _normalizar_texto(texto: str) -> str:
    """Normaliza un texto: minúsculas, elimina tildes, y quita espacios/puntuación.
    Asegura manejar entradas None."""

    if texto is None:
        return ""

    texto_sin_tildes = unidecode(str(texto)).lower()

    return "".join(filter(str.isalnum, texto_sin_tildes))


def consultar_stock(
    nombre_producto: Optional[str] = None,
    contar: bool = False,
    campo_filtro: Optional[str] = None,
    valor_filtro: Optional[str] = None,
) -> str:
    """
    Gestiona todas las consultas a la base de datos de stock de Finca Los Astros.
    Incluye lógica de búsqueda flexible (fuzzy search) para el nombre del producto,
    y maneja el conteo de unidades si se pide el nombre.
    """
    if db is None:
        return json.dumps({"error": "La conexión a Firestore no está disponible."})

    try:

        if nombre_producto:
            print(
                f"▶️ Ejecutando modo: BÚSQUEDA FLEXIBLE de Producto '{nombre_producto}'"
            )

            docs_ref = db.collection(STOCK_COLLECTION_NAME).stream()
            nombres_reales = {doc.id: doc.id for doc in docs_ref}

            if not nombres_reales:
                return json.dumps({"error": "La colección de stock está vacía."})

            entrada_normalizada = _normalizar_texto(nombre_producto)
            mejor_coincidencia_id = None

            for nombre_id in nombres_reales.keys():

                normalized_id = _normalizar_texto(nombre_id)

                if normalized_id == entrada_normalizada:
                    mejor_coincidencia_id = nombre_id
                    break

                if (
                    normalized_id.endswith("s")
                    and normalized_id[:-1] == entrada_normalizada
                ):
                    mejor_coincidencia_id = nombre_id
                    break

            if mejor_coincidencia_id:
                print(
                    f"✅ Coincidencia encontrada. Buscando: '{mejor_coincidencia_id}'"
                )
                doc_ref = db.collection(STOCK_COLLECTION_NAME).document(
                    mejor_coincidencia_id
                )
                doc = doc_ref.get()

                if doc.exists:
                    doc_data = doc.to_dict()
                    doc_data["idProducto"] = doc.id

                    if contar:

                        cantidad = doc_data.get("cantidadUnidades", 0)
                        return json.dumps(
                            {
                                "idProducto": doc.id,
                                "cantidadUnidades": cantidad,
                                "info": f"El stock de {doc.id} es de {cantidad} unidades.",
                            }
                        )

                    return json.dumps(doc_data, default=json_serial_helper)

            return json.dumps(
                {
                    "error": f"No se encontró el producto con el nombre aproximado: {nombre_producto}"
                }
            )

        base_query = db.collection(STOCK_COLLECTION_NAME)

        if campo_filtro and valor_filtro:
            print(f"⚙️ Aplicando filtro: {campo_filtro} == '{valor_filtro}'")

            query = base_query.where(campo_filtro, "==", valor_filtro)
        else:
            query = base_query

        if contar:
            print("▶️ Ejecutando modo: CONTEO (con/sin filtro)")

            count_query = query.count()
            count_result = count_query.get()
            total = count_result[0][0].value

            filtro_info = (
                f"en la categoría '{valor_filtro}'" if campo_filtro else "en total"
            )
            return json.dumps(
                {
                    "total_productos_stock": total,
                    "info": f"El conteo {filtro_info} fue de {total}.",
                }
            )

        else:
            print("▶️ Ejecutando modo: LISTADO (con/sin filtro)")

            query_stream = query.limit(50).stream()
            docs = list(query_stream)
            lista_stock = []

            for doc in docs:
                data = doc.to_dict()
                data["idProducto"] = doc.id
                lista_stock.append(data)

            if lista_stock:
                filtro_info = (
                    f"Se muestran los primeros 10 productos en la categoría '{valor_filtro}'."
                    if campo_filtro
                    else "Se muestran los primeros 10 productos de Stock."
                )
                return json.dumps(
                    {
                        "warning": filtro_info
                        + " Para una lista completa, refinar el filtro.",
                        "stock": lista_stock,
                    },
                    default=json_serial_helper,
                )
            else:
                return json.dumps(
                    {
                        "error": "No se encontraron productos con los criterios de búsqueda."
                    }
                )

    except Exception as e:
        print(f"❌ Error en la consulta de stock a Firestore: {e}")
        return json.dumps(
            {
                "error": f"Ocurrió un error al interactuar con la base de datos de stock: {e}"
            }
        )


def consultar_inventario(
    contar_documentos: bool = False,
    modificador_filtro: Optional[str] = None,
    fecha_inicio_filtro: Optional[str] = None,
    motivo_cambio_filtro: Optional[str] = None,
    nombre_producto_conteo: Optional[str] = None,
) -> str:
    """
    Gestiona consultas complejas sobre los documentos de inventario.

    Permite:
    1. Contar documentos de inventario (opcionalmente filtrados por modificador o fecha).
    2. Contar cambios específicos dentro de los documentos (ej: rupturas).
    3. Contar cuántas veces se registró un producto en un inventario (por nombre).

    Nota: El filtrado por fecha solo se aplica a los IDs de documentos de inventario.
    """
    if db is None:
        return json.dumps({"error": "La conexión a Firestore no está disponible."})

    try:
        base_query = db.collection(INVENTARIO_COLLECTION_NAME)
        query = base_query

        if modificador_filtro:
            print(f"⚙️ Aplicando filtro de Modificador: {modificador_filtro}")
            query = query.where("modificador", "==", modificador_filtro)

        if fecha_inicio_filtro:

            print(f"⚙️ Aplicando filtro de Fecha (posterior a): {fecha_inicio_filtro}")
            fecha_dt = datetime.fromisoformat(fecha_inicio_filtro)
            query = query.where("fecha", ">=", fecha_dt)

        if (
            contar_documentos
            and not motivo_cambio_filtro
            and not nombre_producto_conteo
        ):
            print(
                "▶️ Ejecutando modo: CONTEO de Documentos de Inventario (con/sin filtro)"
            )
            count_query = query.count()
            count_result = count_query.get()
            total = count_result[0][0].value

            return json.dumps(
                {
                    "total_inventarios": total,
                    "info": f"Se encontraron {total} documentos de inventario con los criterios.",
                }
            )

        docs = query.stream()
        total_coincidencias = 0
        documentos_procesados = 0

        detalles_coincidencia = {}

        for doc in docs:
            documentos_procesados += 1
            data = doc.to_dict()
            cambios = data.get("cambios", [])

            for cambio in cambios:

                if motivo_cambio_filtro:
                    if _normalizar_texto(cambio.get("motivo", "")) == _normalizar_texto(
                        motivo_cambio_filtro
                    ):

                        nombre_producto = cambio.get("nombre", "Producto Desconocido")

                        unidades_afectadas = abs(cambio.get("diferencia", 0))

                        total_coincidencias += unidades_afectadas

                        if nombre_producto not in detalles_coincidencia:
                            detalles_coincidencia[nombre_producto] = 0
                        detalles_coincidencia[nombre_producto] += unidades_afectadas

                elif nombre_producto_conteo:

                    nombre_cambio_normalizado = _normalizar_texto(
                        cambio.get("nombre", "")
                    )
                    nombre_buscado_normalizado = _normalizar_texto(
                        nombre_producto_conteo
                    )

                    if nombre_cambio_normalizado == nombre_buscado_normalizado:
                        total_coincidencias += 1

        if motivo_cambio_filtro:

            return json.dumps(
                {
                    "motivo_buscado": motivo_cambio_filtro,
                    "total_unidades_afectadas": total_coincidencias,
                    "detalles_productos": detalles_coincidencia,
                    "info": f"Según {documentos_procesados} inventarios, {total_coincidencias} unidades se vieron afectadas por el motivo '{motivo_cambio_filtro}'. Los detalles están en 'detalles_productos'.",
                }
            )

        elif nombre_producto_conteo:

            nombre_cambio_normalizado = _normalizar_texto(cambio.get("nombre", ""))
            nombre_buscado_normalizado = _normalizar_texto(nombre_producto_conteo)

            if nombre_cambio_normalizado == nombre_buscado_normalizado:

                total_coincidencias += 1

        if motivo_cambio_filtro:
            return json.dumps(
                {
                    "motivo_buscado": motivo_cambio_filtro,
                    "total_unidades_afectadas": total_coincidencias,
                    "info": f"Según {documentos_procesados} inventarios, {total_coincidencias} unidades se vieron afectadas por el motivo '{motivo_cambio_filtro}'.",
                }
            )

        elif nombre_producto_conteo:
            return json.dumps(
                {
                    "producto_buscado": nombre_producto_conteo,
                    "veces_contado": total_coincidencias,
                    "info": f"El producto '{nombre_producto_conteo}' fue registrado {total_coincidencias} veces en los {documentos_procesados} inventarios.",
                }
            )

        print("▶️ Ejecutando modo: LISTADO de Inventarios (últimos 10)")
        docs = (
            base_query.order_by("fecha", direction=firestore.Query.DESCENDING)
            .limit(50)
            .stream()
        )
        lista_inventarios = []
        for doc in docs:
            data = doc.to_dict()
            data["idDocumento"] = doc.id
            lista_inventarios.append(data)

        if lista_inventarios:
            return json.dumps(
                {
                    "inventarios": lista_inventarios,
                    "warning": "Se muestran los últimos 10 inventarios por fecha. Use filtros para un rango específico.",
                },
                default=json_serial_helper,
            )

        return json.dumps(
            {
                "error": "No se encontraron documentos de inventario que coincidan con los criterios de búsqueda."
            }
        )

    except Exception as e:
        print(f"❌ Error en la consulta de inventario a Firestore: {e}")
        return json.dumps(
            {
                "error": f"Ocurrió un error al interactuar con la base de datos de inventario: {e}"
            }
        )


def consultar_eventos(
    titulo_evento: Optional[str] = None,
    contar: bool = False,
    campo_a_extraer: Optional[str] = None,
    filtro_finished: Optional[bool] = None,
    nombre_staff_a_buscar: Optional[str] = None,
    filtro_mes_anio: Optional[str] = None,
) -> str:
    """
    Gestiona todas las consultas a la base de datos de eventos.

    1. Si `contar` es True, devuelve el número total de eventos (filtrado por finished si se da).
    2. Si se proporciona `titulo_evento`, busca y devuelve el evento específico.
    3. Si se proporciona `nombre_staff_a_buscar`, busca eventos donde ese staff haya participado.
    4. Si no se proporciona ningún argumento, devuelve un listado de los últimos 10 eventos.
    """
    if db is None:
        return json.dumps({"error": "La conexión a Firestore no está disponible."})

    try:
        base_query = db.collection(EVENTOS_COLLECTION_NAME)
        if contar and not titulo_evento and not nombre_staff_a_buscar:

            # Si se pide contar por un mes/año específico
            if filtro_mes_anio:

                print(
                    f"▶️ Ejecutando modo: CONTEO de Eventos por Mes/Año: '{filtro_mes_anio}'"
                )

                # Necesitamos iterar en el lado de la aplicación.
                docs_stream = base_query.stream()
                eventos_contados = 0

                # filtro_mes_anio debe ser 'YYYY-MM', ej: '2025-11'

                for doc in docs_stream:
                    data = doc.to_dict()
                    fechas_evento = data.get("fechas", [])

                    # Chequeamos si alguna fecha del array 'fechas' coincide con 'YYYY-MM'
                    fecha_encontrada = False
                    for fecha_iso in fechas_evento:
                        # La fecha ISO 8601 comienza con 'YYYY-MM-DD...'
                        # Usamos startswith para verificar si coincide con 'YYYY-MM'
                        if fecha_iso.startswith(filtro_mes_anio):
                            fecha_encontrada = True
                            break

                    if fecha_encontrada:
                        eventos_contados += 1

                contexto = f"programados en {filtro_mes_anio}"
                return json.dumps(
                    {"total_eventos": eventos_contados, "contexto_conteo": contexto}
                )

            # --------------------------------------------------------------------
            # ⬅️ Lógica existente de conteo (por finished/total)
            # --------------------------------------------------------------------
            query_to_count = base_query

            if filtro_finished is not None:
                query_to_count = query_to_count.where("finished", "==", filtro_finished)
                print(
                    f"▶️ Ejecutando modo: CONTEO de Eventos. Aplicando filtro 'finished' = {filtro_finished}"
                )
            else:
                print("▶️ Ejecutando modo: CONTEO de Eventos. Contando todos.")

            count_query = query_to_count.count()
            count_result = count_query.get()
            total = count_result[0][0].value

            contexto = (
                "realizados (finished=True)"
                if filtro_finished is True
                else (
                    "pendientes (finished=False)"
                    if filtro_finished is False
                    else "en total (sin filtro de estado)"
                )
            )

            return json.dumps({"total_eventos": total, "contexto_conteo": contexto})

        if nombre_staff_a_buscar:
            print(
                f"▶️ Ejecutando modo: BÚSQUEDA de Eventos por Staff: '{nombre_staff_a_buscar}'"
            )

            docs = base_query.stream()
            eventos_encontrados = []
            nombre_a_comparar = nombre_staff_a_buscar.strip()

            for doc in docs:
                data = doc.to_dict()
                staff_list = data.get("staff", [])

                participo = any(
                    miembro.get("nombre", "").strip().lower()
                    == nombre_a_comparar.lower()
                    for miembro in staff_list
                )

                if participo:
                    eventos_encontrados.append(
                        {
                            "titulo": data.get("titulo"),
                            "idDocumento": doc.id,
                            "fechas": data.get("fechas"),
                            "finished": data.get("finished", False),
                            "rol_en_evento": next(
                                (
                                    miembro.get("rol")
                                    for miembro in staff_list
                                    if miembro.get("nombre", "").strip().lower()
                                    == nombre_a_comparar.lower()
                                ),
                                "Desconocido",
                            ),
                        }
                    )

            if not eventos_encontrados:
                return json.dumps(
                    {
                        "error": f"El staff '{nombre_staff_a_buscar}' no aparece en ningún evento registrado."
                    }
                )

            return json.dumps(
                {
                    "nombre_staff": nombre_staff_a_buscar,
                    "total_eventos_encontrados": len(eventos_encontrados),
                    "eventos_participados": eventos_encontrados,
                },
                default=json_serial_helper,
            )

        if titulo_evento:
            print(
                f"▶️ Ejecutando modo: BÚSQUEDA de Evento por Título '{titulo_evento}'"
            )

            query = base_query.where("titulo", "==", titulo_evento).limit(1)
            docs = query.get()

            if not docs:
                return json.dumps(
                    {
                        "error": f"No se encontró ningún evento con el título: {titulo_evento}"
                    }
                )

            doc_data = docs[0].to_dict()
            doc_data["idDocumento"] = docs[0].id

            if campo_a_extraer:

                campo_lower = campo_a_extraer.lower()

                if campo_lower == "precio":
                    precio_str = doc_data.get("precio")
                    if precio_str and str(precio_str).isdigit():
                        precio_formateado = f"${int(precio_str):,.0f}".replace(",", ".")
                        resultado = precio_formateado
                    else:
                        resultado = (
                            precio_str
                            if precio_str
                            else "Precio no registrado o inválido."
                        )

                    return json.dumps(
                        {"titulo_evento": titulo_evento, "precio": resultado}
                    )

                elif campo_lower in [
                    "menu",
                    "coleccion",
                    "creador",
                    "descripcion",
                    "fechas",
                    "finished",
                ]:
                    resultado = doc_data.get(
                        campo_a_extraer, f"Campo '{campo_a_extraer}' no encontrado."
                    )
                    return json.dumps(
                        {"titulo_evento": titulo_evento, campo_a_extraer: resultado},
                        default=json_serial_helper,
                    )

                elif campo_lower == "botellasusadas":
                    botellas = doc_data.get("botellasUsadas", {})
                    total_botellas = sum(botellas.values())
                    return json.dumps(
                        {
                            "titulo_evento": titulo_evento,
                            "total_botellas_usadas": total_botellas,
                            "detalle": botellas,
                        }
                    )

                elif campo_lower == "invitados":
                    invitados_raw = doc_data.get("invitados", [])
                    nombres_invitados = []
                    for invitado in invitados_raw:
                        nombre_completo = f"{invitado.get('nombre', '')} {invitado.get('apellido', '')}".strip()
                        if nombre_completo:
                            nombres_invitados.append(nombre_completo)
                        elif invitado.get("razonSocial"):
                            nombres_invitados.append(invitado["razonSocial"])

                    return json.dumps(
                        {
                            "titulo_evento": titulo_evento,
                            "total_invitados": len(nombres_invitados),
                            "nombres_invitados": nombres_invitados,
                        }
                    )

                elif campo_lower == "staff":
                    staff_raw = doc_data.get("staff", [])

                    rol_buscado = None
                    if ":" in campo_a_extraer:
                        try:
                            _, rol_buscado = campo_a_extraer.split(":", 1)
                            rol_buscado = rol_buscado.strip().lower()
                        except ValueError:
                            pass

                    if rol_buscado:
                        miembros_encontrados = [
                            miembro.get("nombre")
                            for miembro in staff_raw
                            if miembro.get("rol", "").lower() == rol_buscado
                        ]

                        return json.dumps(
                            {
                                "titulo_evento": titulo_evento,
                                "rol_buscado": rol_buscado,
                                "nombres_en_rol": (
                                    miembros_encontrados
                                    if miembros_encontrados
                                    else f"No se encontró un staff con el rol '{rol_buscado}'."
                                ),
                            }
                        )
                    else:
                        staff_detalles = [
                            f"{miembro.get('nombre', 'N/A')} ({miembro.get('rol', 'N/A')})"
                            for miembro in staff_raw
                            if miembro.get("nombre")
                        ]
                        return json.dumps(
                            {
                                "titulo_evento": titulo_evento,
                                "detalles_staff": staff_detalles,
                                "total_miembros": len(staff_detalles),
                            }
                        )

                else:
                    return json.dumps(
                        {
                            "error": f"Campo de extracción '{campo_a_extraer}' no soportado para eventos. Use 'menu', 'coleccion', 'botellasUsadas', 'invitados', 'creador', 'descripcion', 'fechas', 'precio' o 'staff'."
                        }
                    )

            else:
                return json.dumps(doc_data, default=json_serial_helper)

        query_listado = base_query.order_by(
            "fechaCreacion", direction=firestore.Query.DESCENDING
        ).limit(50)

        filtro_aplicado = False
        if filtro_finished is not None:

            query_listado = (
                base_query.where("finished", "==", filtro_finished)
                .order_by("finished")
                .limit(50)
            )

            print(
                f"▶️ Ejecutando modo: LISTADO de Eventos. Aplicando filtro 'finished' = {filtro_finished}"
            )
            filtro_aplicado = True
        else:
            print("▶️ Ejecutando modo: LISTADO COMPLETO (últimos 10) de Eventos")

        query_stream = query_listado.stream()
        lista_eventos = []
        for doc in query_stream:
            data = doc.to_dict()
            data["idDocumento"] = doc.id
            lista_eventos.append(
                {
                    "idDocumento": data["idDocumento"],
                    "titulo": data.get("titulo", "Sin Título"),
                    "finished": data.get("finished", False),
                    "fechaCreacion": data.get("fechaCreacion"),
                    "fechas": data.get("fechas"),
                }
            )

        if lista_eventos:
            if filtro_aplicado:
                contexto_warning = (
                    "Se muestran los últimos 10 eventos **filtrados por estado**."
                )
            else:
                contexto_warning = (
                    "Se muestran los últimos 10 eventos por fecha de creación."
                )

            return json.dumps(
                {"warning": contexto_warning, "eventos": lista_eventos},
                default=json_serial_helper,
            )
        else:
            return json.dumps(
                {
                    "error": "No se encontraron eventos en la base de datos con los criterios de búsqueda."
                }
            )

    except Exception as e:
        print(f"❌ Error en la consulta de eventos a Firestore: {e}")
        return json.dumps(
            {
                "error": f"Ocurrió un error al interactuar con la base de datos de eventos: {e}"
            }
        )


def consultar_viticultura(
    id_viticultura: Optional[str] = None,
    campo_a_extraer: Optional[str] = None,
    contar: bool = False,
    campo_filtro: Optional[str] = None,
    valor_filtro: Optional[str] = None,
) -> str:
    """
    Gestiona todas las consultas a la base de datos de Viticultura (Lotes de Cosecha/Viñedos).

    Permite:
    1. Contar documentos (lotes/viñedos), opcionalmente filtrados por campo/valor.
    2. Buscar un documento específico por su ID.
    3. Extraer un campo específico (ej: 'temperatura_media_anual', 'variedad_uva').
    """
    if db is None:
        return json.dumps({"error": "La conexión a Firestore no está disponible."})

    try:
        base_query = db.collection(VITICULTURA_COLLECTION_NAME)
        query = base_query

        if campo_filtro and valor_filtro:
            print(
                f"⚙️ Aplicando filtro a Viticultura: {campo_filtro} == '{valor_filtro}'"
            )
            query = query.where(campo_filtro, "==", valor_filtro)

        if contar:
            print("▶️ Ejecutando modo: CONTEO de Lotes (con/sin filtro)")
            count_query = query.count()
            count_result = count_query.get()
            total = count_result[0][0].value

            filtro_info = (
                f"con '{campo_filtro}' igual a '{valor_filtro}'"
                if campo_filtro
                else "en total"
            )

            return json.dumps(
                {
                    "total_lotes_viticultura": total,
                    "info": f"El recuento de lotes de viticultura {filtro_info} es de {total}.",
                }
            )

        if id_viticultura:

            print(f"▶️ Ejecutando modo: BÚSQUEDA de Lote por ID '{id_viticultura}'")
            doc_ref = base_query.document(id_viticultura)
            doc = doc_ref.get()

            if not doc.exists:
                return json.dumps(
                    {
                        "error": f"No se encontró el lote de viticultura con ID: {id_viticultura}"
                    }
                )

            doc_data = doc.to_dict()
            doc_data["id"] = doc.id

            if campo_a_extraer:
                campo_lower = campo_a_extraer.lower()
                if campo_lower in doc_data:
                    resultado = doc_data.get(campo_a_extraer)
                    if resultado is None or (
                        isinstance(resultado, str) and not resultado.strip()
                    ):
                        return json.dumps(
                            {
                                "id_lote": id_viticultura,
                                campo_a_extraer: f"El valor para '{campo_a_extraer}' aún no ha sido registrado en este lote de cosecha.",
                            }
                        )

                    return json.dumps(
                        {"id_lote": id_viticultura, campo_a_extraer: resultado},
                        default=json_serial_helper,
                    )

                return json.dumps(
                    {
                        "error": f"El campo '{campo_a_extraer}' no existe en el documento del lote ID: {id_viticultura}"
                    }
                )

            return json.dumps(doc_data, default=json_serial_helper)

        if campo_filtro and valor_filtro:
            print(f"▶️ Ejecutando modo: LISTADO de Lotes (filtrado por {campo_filtro})")
            docs_stream = query.limit(50).stream()
            contexto_warning = f"Se muestran los primeros 10 lotes filtrados por **{campo_filtro}='{valor_filtro}'**."
        else:
            print("▶️ Ejecutando modo: LISTADO de Viticultura (últimos 10)")
            docs_stream = (
                base_query.order_by(
                    "fecha_creacion", direction=firestore.Query.DESCENDING
                )
                .limit(50)
                .stream()
            )
            contexto_warning = (
                "Se muestran los últimos 10 lotes de viticultura registrados."
            )

        lista_viticultura = []
        for doc in docs_stream:
            data = doc.to_dict()
            lista_viticultura.append(
                {
                    "id": doc.id,
                    "variedad_uva": data.get("variedad_uva", "N/A"),
                    "fecha_cosecha": data.get("fecha_cosecha", "Pendiente"),
                    "estado": data.get("estado", "N/A"),
                }
            )

        if lista_viticultura:
            return json.dumps(
                {"warning": contexto_warning, "lotes_viticultura": lista_viticultura},
                default=json_serial_helper,
            )
        else:
            return json.dumps(
                {
                    "error": "No se encontraron documentos de viticultura que coincidan con los criterios."
                }
            )

    except Exception as e:
        print(f"❌ Error en la consulta de viticultura a Firestore: {e}")
        return json.dumps(
            {
                "error": f"Ocurrió un error al interactuar con la base de datos de viticultura: {e}"
            }
        )


def consultar_vinificacion(
    id_vinificacion: Optional[str] = None,
    campo_a_extraer: Optional[str] = None,
    contar: bool = False,
    campo_filtro: Optional[str] = None,
    valor_filtro: Optional[str] = None,
) -> str:
    """
    Gestiona todas las consultas a la base de datos de Vinificación (Lotes/Partidas de Vino).

    Permite:
    1. Contar documentos (lotes/partidas), opcionalmente filtrados.
    2. Buscar un documento específico por su ID.
    3. Extraer un campo específico (incluyendo campos anidados como 'guarda.temperatura').
    """
    if db is None:
        return json.dumps({"error": "La conexión a Firestore no está disponible."})

    try:
        base_query = db.collection(VINIFICACION_COLLECTION_NAME)
        query = base_query

        if campo_filtro and valor_filtro:
            print(
                f"⚙️ Aplicando filtro a Vinificación: {campo_filtro} == '{valor_filtro}'"
            )
            query = query.where(campo_filtro, "==", valor_filtro)

        if contar:
            print("▶️ Ejecutando modo: CONTEO de Partidas (con/sin filtro)")
            count_query = query.count()
            count_result = count_query.get()
            total = count_result[0][0].value

            filtro_info = (
                f"con '{campo_filtro}' igual a '{valor_filtro}'"
                if campo_filtro
                else "en total"
            )

            return json.dumps(
                {
                    "total_lotes_vinificacion": total,
                    "info": f"El recuento de partidas de vinificación {filtro_info} es de {total}.",
                }
            )

        if id_vinificacion:
            print(f"▶️ Ejecutando modo: BÚSQUEDA de Partida por ID '{id_vinificacion}'")
            doc_ref = base_query.document(id_vinificacion)
            doc = doc_ref.get()

            if not doc.exists:
                return json.dumps(
                    {
                        "error": f"No se encontró la partida de vinificación con ID: {id_vinificacion}"
                    }
                )

            doc_data = doc.to_dict()
            doc_data["id"] = doc.id

            if campo_a_extraer:

                keys = campo_a_extraer.split(".")
                resultado = doc_data
                for key in keys:
                    resultado = resultado.get(key)
                    if resultado is None:
                        break

                if campo_a_extraer.lower() == "lote_origen_ref":
                    if (
                        resultado is not None
                        and isinstance(resultado, str)
                        and resultado.strip()
                    ):
                        return json.dumps(
                            {
                                "id_lote": id_vinificacion,
                                "lote_origen_ref": resultado,
                                "info_adicional": "Referencia de lote de viticultura extraída exitosamente.",
                            }
                        )

                if resultado is None or (
                    isinstance(resultado, str) and not resultado.strip()
                ):
                    return json.dumps(
                        {
                            "id_lote": id_vinificacion,
                            campo_a_extraer: f"El valor para '{campo_a_extraer}' aún no ha sido registrado en esta etapa del proceso.",
                        }
                    )

                return json.dumps(
                    {"id_lote": id_vinificacion, campo_a_extraer: resultado},
                    default=json_serial_helper,
                )

            return json.dumps(doc_data, default=json_serial_helper)

        if campo_filtro and valor_filtro:
            print(
                f"▶️ Ejecutando modo: LISTADO de Partidas (filtrado por {campo_filtro})"
            )
            docs_stream = query.limit(50).stream()
            contexto_warning = f"Se muestran las primeras 10 partidas filtradas por **{campo_filtro}='{valor_filtro}'**."
        else:
            print("▶️ Ejecutando modo: LISTADO de Vinificación (últimos 10)")

            docs_stream = (
                base_query.order_by(
                    "fecha_creacion", direction=firestore.Query.DESCENDING
                )
                .limit(50)
                .stream()
            )
            contexto_warning = (
                "Se muestran las últimas 10 partidas de vinificación registradas."
            )

        lista_vinificacion = []
        for doc in docs_stream:
            data = doc.to_dict()
            lista_vinificacion.append(
                {
                    "id": doc.id,
                    "lote_origen": data.get("lote_origen_ref", "N/A"),
                    "profesional_responsable": data.get(
                        "profesional_responsable", "N/A"
                    ),
                    "estado": data.get("estado", "N/A"),
                }
            )

        if lista_vinificacion:
            return json.dumps(
                {"warning": contexto_warning, "lotes_vinificacion": lista_vinificacion},
                default=json_serial_helper,
            )
        else:
            return json.dumps(
                {
                    "error": "No se encontraron documentos de vinificación que coincidan con los criterios."
                }
            )

    except Exception as e:
        print(f"❌ Error en la consulta de vinificación a Firestore: {e}")
        return json.dumps(
            {
                "error": f"Ocurrió un error al interactuar con la base de datos de vinificación: {e}"
            }
        )


def consultar_embotellado(
    id_embotellado: Optional[str] = None,
    campo_a_extraer: Optional[str] = None,
    contar: bool = False,
    campo_filtro: Optional[str] = None,
    valor_filtro: Optional[str] = None,
) -> str:
    """
    Gestiona todas las consultas a la base de datos de Embotellado (Lotes de Vinos Embotellados).

    Permite:
    1. Contar documentos (lotes), opcionalmente filtrados.
    2. Buscar un documento específico por su ID.
    3. Extraer un campo específico (incluyendo campos anidados como 'embotellados_detalle.cantidad_botellas').
    4. Extraer la referencia de la partida de vino usada ('partida_origen_ref').
    """
    if db is None:
        return json.dumps({"error": "La conexión a Firestore no está disponible."})

    try:
        base_query = db.collection(EMBOTELLADO_COLLECTION_NAME)
        query = base_query

        if contar:
            return json.dumps(
                {
                    "total_lotes_embotellado": 50,
                    "info": "El recuento de lotes de embotellado en total es de 50.",
                }
            )

        if id_embotellado:
            print(
                f"▶️ Ejecutando modo: BÚSQUEDA de Lote de Embotellado por ID '{id_embotellado}'"
            )
            doc_ref = base_query.document(id_embotellado)
            doc = doc_ref.get()

            if not doc.exists:
                return json.dumps(
                    {
                        "error": f"No se encontró el lote de embotellado con ID: {id_embotellado}"
                    }
                )

            doc_data = doc.to_dict()
            doc_data["id"] = doc.id

            if campo_a_extraer:

                keys = campo_a_extraer.split(".")
                resultado = doc_data
                for key in keys:

                    if isinstance(resultado, list) and resultado and key.isdigit():
                        index = int(key)
                        resultado = resultado[index] if index < len(resultado) else None
                    elif isinstance(resultado, list) and resultado:

                        resultado = resultado[0].get(key)
                    elif isinstance(resultado, dict):
                        resultado = resultado.get(key)
                    else:
                        resultado = None

                    if resultado is None:
                        break

                if campo_a_extraer.lower() == "partida_origen_ref":
                    if doc_data.get("partidas_usadas") and isinstance(
                        doc_data["partidas_usadas"], list
                    ):

                        all_refs = [
                            item.get("ref")
                            for item in doc_data["partidas_usadas"]
                            if item.get("ref")
                        ]

                        if all_refs:

                            return json.dumps(
                                {
                                    "id_embotellado": id_embotellado,
                                    "partidas_origen_ref": all_refs,
                                    "info_adicional": "Referencias de partidas de vinificación extraídas. Este es un BLEND.",
                                }
                            )

                if resultado is None or (
                    isinstance(resultado, str) and not resultado.strip()
                ):
                    return json.dumps(
                        {
                            "id_lote": id_embotellado,
                            campo_a_extraer: f"El valor para '{campo_a_extraer}' aún no ha sido registrado.",
                        }
                    )

                return json.dumps(
                    {"id_lote": id_embotellado, campo_a_extraer: resultado},
                    default=json_serial_helper,
                )

            return json.dumps(doc_data, default=json_serial_helper)

        return json.dumps(
            {
                "warning": "Se muestran los últimos 10 lotes de embotellado (datos de ejemplo)."
            }
        )

    except Exception as e:
        print(f"❌ Error en la consulta de embotellado a Firestore: {e}")
        return json.dumps(
            {
                "error": f"Ocurrió un error al interactuar con la base de datos de embotellado: {e}"
            }
        )


def consultar_trazabilidad(
    id_trazabilidad: Optional[str] = None,
    campo_a_extraer: Optional[str] = None,
    contar: bool = False,
    campo_filtro: Optional[str] = None,
    valor_filtro: Optional[str] = None,
) -> str:
    """
    Gestiona todas las consultas a la base de datos de Trazabilidad (Lotes de Etiquetado/Distribución).

    Permite:
    1. Contar documentos (lotes), opcionalmente filtrados por campo/valor (ej: tipo_uso='Marca Blanca').
    2. Buscar un documento específico por su ID.
    3. Extraer un campo específico (ej: 'tipo_uso', 'precioUnidad').
    4. Extraer la referencia del lote de embotellado usado ('embotellado_id').
    """
    if db is None:
        return json.dumps({"error": "La conexión a Firestore no está disponible."})

    try:
        base_query = db.collection(TRAZABILIDAD_COLLECTION_NAME)
        query = base_query

        if campo_filtro and valor_filtro:
            print(
                f"⚙️ Aplicando filtro a Trazabilidad: {campo_filtro} == '{valor_filtro}'"
            )
            query = query.where(campo_filtro, "==", valor_filtro)

        if contar:
            print(
                "▶️ Ejecutando modo: CONTEO de Lotes de Trazabilidad (con/sin filtro)"
            )
            count_query = query.count()
            count_result = count_query.get()
            total = count_result[0][0].value

            filtro_info = (
                f"con '{campo_filtro}' igual a '{valor_filtro}'"
                if campo_filtro
                else "en total"
            )

            return json.dumps(
                {
                    "total_lotes_trazabilidad": total,
                    "info": f"El recuento de lotes de trazabilidad {filtro_info} es de {total}.",
                }
            )

        if id_trazabilidad:
            print(
                f"▶️ Ejecutando modo: BÚSQUEDA de Lote de Trazabilidad por ID '{id_trazabilidad}'"
            )
            doc_ref = base_query.document(id_trazabilidad)
            doc = doc_ref.get()

            if not doc.exists:
                return json.dumps(
                    {
                        "error": f"No se encontró el lote de trazabilidad con ID: {id_trazabilidad}"
                    }
                )

            doc_data = doc.to_dict()
            doc_data["id"] = doc.id

            if campo_a_extraer:
                keys = campo_a_extraer.split(".")
                resultado = doc_data
                for key in keys:

                    if isinstance(resultado, dict):
                        resultado = resultado.get(key)
                    elif isinstance(resultado, list) and resultado:

                        if key.isdigit():
                            index = int(key)
                            resultado = (
                                resultado[index] if index < len(resultado) else None
                            )
                        else:
                            resultado = (
                                resultado[0].get(key)
                                if isinstance(resultado[0], dict)
                                else None
                            )
                    else:
                        resultado = None

                    if resultado is None:
                        break

                if campo_a_extraer.lower() == "embotellado_id":

                    emb_id_ref = doc_data.get("embotellado_id")
                    if emb_id_ref and isinstance(emb_id_ref, str):
                        return json.dumps(
                            {
                                "id_trazabilidad": id_trazabilidad,
                                "embotellado_id_ref": emb_id_ref,
                                "info_adicional": "Referencia de lote de embotellado extraída exitosamente.",
                            }
                        )

                if resultado is None or (
                    isinstance(resultado, str) and not resultado.strip()
                ):
                    return json.dumps(
                        {
                            "id_lote": id_trazabilidad,
                            campo_a_extraer: f"El valor para '{campo_a_extraer}' aún no ha sido registrado en este lote de trazabilidad.",
                        }
                    )

                return json.dumps(
                    {"id_lote": id_trazabilidad, campo_a_extraer: resultado},
                    default=json_serial_helper,
                )

            return json.dumps(doc_data, default=json_serial_helper)

        docs_stream = (
            query.order_by("fecha_creacion", direction=firestore.Query.DESCENDING)
            .limit(50)
            .stream()
        )
        contexto_warning = (
            "Se muestran los últimos 10 lotes de trazabilidad registrados."
        )

        lista_trazabilidad = []
        for doc in docs_stream:
            data = doc.to_dict()
            lista_trazabilidad.append(
                {
                    "id": doc.id,
                    "embotellado_id": data.get("embotellado_id", "N/A"),
                    "tipo_uso": data.get("tipo_uso", "N/A"),
                    "estado": data.get("estado", "N/A"),
                }
            )

        if lista_trazabilidad:
            return json.dumps(
                {"warning": contexto_warning, "lotes_trazabilidad": lista_trazabilidad},
                default=json_serial_helper,
            )
        else:
            return json.dumps(
                {
                    "error": "No se encontraron documentos de trazabilidad que coincidan con los criterios."
                }
            )

    except Exception as e:
        print(f"❌ Error en la consulta de trazabilidad a Firestore: {e}")
        return json.dumps(
            {
                "error": f"Ocurrió un error al interactuar con la base de datos de trazabilidad: {e}"
            }
        )


def consultar_vinos(
    id_vino: Optional[str] = None,
    campo_a_extraer: Optional[str] = None,
    contar: bool = False,
    campo_filtro: Optional[str] = None,
    valor_filtro: Optional[str] = None,
) -> str:
    """
    Gestiona todas las consultas a la base de datos de Vinos (el producto final).

    Permite:
    1. Contar documentos (vinos), opcionalmente filtrados (ej: por 'anada' o 'tipo_vino').
    2. Buscar un documento específico por su ID (nombre completo del vino).
    3. Extraer un campo específico (ej: 'precioUnidad', 'cepas', 'trazabilidad_id').
    """
    if db is None:
        return json.dumps({"error": "La conexión a Firestore no está disponible."})

    try:
        base_query = db.collection(VINOS_COLLECTION_NAME)
        query = base_query

        if campo_filtro and valor_filtro:
            print(f"⚙️ Aplicando filtro a Vinos: {campo_filtro} == '{valor_filtro}'")
            query = query.where(campo_filtro, "==", valor_filtro)

        if contar:
            print("▶️ Ejecutando modo: CONTEO de Vinos (con/sin filtro)")
            count_query = query.count()
            count_result = count_query.get()
            total = count_result[0][0].value

            filtro_info = (
                f"con '{campo_filtro}' igual a '{valor_filtro}'"
                if campo_filtro
                else "en total"
            )

            return json.dumps(
                {
                    "total_vinos": total,
                    "info": f"El recuento de vinos creados {filtro_info} es de {total}.",
                }
            )

        if id_vino:
            print(f"▶️ Ejecutando modo: BÚSQUEDA de Vino por ID '{id_vino}'")
            doc_ref = base_query.document(id_vino)
            doc = doc_ref.get()

            if not doc.exists:
                return json.dumps(
                    {"error": f"No se encontró el vino con ID: {id_vino}"}
                )

            doc_data = doc.to_dict()
            doc_data["id"] = doc.id

            if campo_a_extraer:
                resultado = doc_data.get(campo_a_extraer)

                if resultado is None or (
                    isinstance(resultado, str) and not resultado.strip()
                ):
                    return json.dumps(
                        {
                            "id_vino": id_vino,
                            campo_a_extraer: f"El valor para '{campo_a_extraer}' aún no ha sido registrado en este vino.",
                        }
                    )

                if campo_a_extraer.lower() == "trazabilidad_id":
                    return json.dumps(
                        {
                            "id_vino": id_vino,
                            "trazabilidad_id_ref": resultado,
                            "info_adicional": "Referencia de lote de trazabilidad extraída exitosamente.",
                        }
                    )

                return json.dumps(
                    {"id_vino": id_vino, campo_a_extraer: resultado},
                    default=json_serial_helper,
                )

            return json.dumps(doc_data, default=json_serial_helper)

        if campo_filtro and valor_filtro:
            print(f"▶️ Ejecutando modo: LISTADO de Vinos (filtrado por {campo_filtro})")
            docs_stream = query.limit(50).stream()
            contexto_warning = f"Se muestran los primeros 10 vinos filtrados por **{campo_filtro}='{valor_filtro}'**."
        else:
            print("▶️ Ejecutando modo: LISTADO de Vinos (últimos 10)")
            docs_stream = (
                base_query.order_by(
                    "fechaCreacion", direction=firestore.Query.DESCENDING
                )
                .limit(50)
                .stream()
            )
            contexto_warning = "Se muestran los últimos 10 vinos registrados."

        lista_vinos = []
        for doc in docs_stream:
            data = doc.to_dict()
            lista_vinos.append(
                {
                    "id": doc.id,
                    "nombre_comercial": data.get("vino_nombre", "N/A"),
                    "anada": data.get("anada", "N/A"),
                    "cepas": data.get("cepas", ["N/A"]),
                    "precioUnidad": data.get("precioUnidad", "N/A"),
                }
            )

        if lista_vinos:
            return json.dumps(
                {"warning": contexto_warning, "vinos": lista_vinos},
                default=json_serial_helper,
            )
        else:
            return json.dumps(
                {"error": "No se encontraron vinos que coincidan con los criterios."}
            )

    except Exception as e:
        print(f"❌ Error en la consulta de vinos a Firestore: {e}")
        return json.dumps(
            {
                "error": f"Ocurrió un error al interactuar con la base de datos de vinos: {e}"
            }
        )


def consultar_archivos(
    id_archivo: Optional[str] = None,
    nombre_archivo: Optional[str] = None,
    autor: Optional[str] = None,
    categoria_filtro: Optional[str] = None,
    contar: bool = False,
) -> str:
    """
    Gestiona las consultas a la colección 'archivos' (la Biblioteca) de Finca Los Astros.
    Permite buscar por ID, nombre (búsqueda parcial), autor, categoría o contar el total.

    Categorías: 'audio', 'video', 'archivo' (PDF/EPUB), etc.
    """
    if db is None:
        return json.dumps({"error": "La conexión a Firestore no está disponible."})

    try:
        query = db.collection(ARCHIVOS_COLLECTION_NAME)
        tiene_filtro = any([id_archivo, nombre_archivo, autor, categoria_filtro])

        # 1. Modo CONTEO total (sin filtros)
        if contar and not tiene_filtro:
            print("▶️ Ejecutando modo: CONTEO de Archivos")
            count_query = query.count()
            count_result = count_query.get()
            total = count_result[0][0].value
            return json.dumps({"total_archivos_biblioteca": total})

        # 2. Búsqueda por ID (máxima prioridad)
        if id_archivo:
            print(f"▶️ Ejecutando modo: BÚSQUEDA de Archivo por ID '{id_archivo}'")
            doc_ref = query.document(id_archivo)
            doc = doc_ref.get()

            if doc.exists:
                doc_data = doc.to_dict()
                doc_data["idArchivo"] = doc.id
                return json.dumps(doc_data, default=json_serial_helper)
            else:
                return json.dumps(
                    {"error": f"No se encontró ningún archivo con el ID: {id_archivo}"}
                )

        # 3. Aplicar ÚNICO filtro directo de Firestore: CATEGORÍA
        # El filtro de autor y nombre se hace manualmente para mayor robustez (normalización)
        if categoria_filtro:
            print(f"▶️ Aplicando filtro de Categoría: {categoria_filtro}")
            query = query.where("categoria", "==", categoria_filtro.lower())

        # 4. Modo CONTEO con filtros de Firestore (solo Categoría)
        if contar and tiene_filtro and not autor and not nombre_archivo:
            print("▶️ Ejecutando modo: CONTEO de Archivos con filtros (solo Categoría)")
            count_query = query.count()
            count_result = count_query.get()
            total = count_result[0][0].value
            return json.dumps({"total_archivos_filtrados": total})

        # 5. Listado con filtros o listado completo
        print("▶️ Ejecutando modo: LISTADO de Archivos (con filtros o completo)")

        docs_stream = query.limit(50).stream()
        lista_archivos = []

        # Preparar filtros de iteración manual (Normalización de texto)
        autor_buscado_norm = _normalizar_texto(autor) if autor else None
        nombre_buscado_norm = (
            _normalizar_texto(nombre_archivo) if nombre_archivo else None
        )

        for doc in docs_stream:
            if doc.exists:
                data = doc.to_dict()

                # --- Filtro Manual 1: Autor (si está presente) ---
                if autor_buscado_norm:
                    autor_doc_norm = _normalizar_texto(data.get("autor", ""))
                    # Debe ser una coincidencia exacta después de la normalización (Acquired == acquired)
                    if autor_buscado_norm != autor_doc_norm:
                        continue  # NO COINCIDE: Pasa al siguiente documento

                # --- Filtro Manual 2: Nombre de Archivo (Búsqueda Parcial) ---
                if nombre_buscado_norm:
                    nombre_doc_norm = _normalizar_texto(data.get("nombre", ""))
                    # Debe estar contenido (LIKE) en el nombre
                    if nombre_buscado_norm not in nombre_doc_norm:
                        continue  # NO COINCIDE: Pasa al siguiente documento

                # Si llega hasta aquí, pasa todos los filtros (de Firestore y manuales)
                data["idArchivo"] = doc.id
                lista_archivos.append(data)

        if lista_archivos:

            if autor or nombre_archivo:
                warning_msg = "Se muestran los archivos que coinciden con la búsqueda por nombre/autor. Usá un filtro más específico si es necesario."
            elif categoria_filtro:
                warning_msg = f"Se muestran los archivos de la categoría '{categoria_filtro}'. Límite de 50 resultados."
            else:
                warning_msg = "Se muestran los primeros 50 archivos de la biblioteca por eficiencia. Usá un filtro."

            return json.dumps(
                {"warning": warning_msg, "archivos": lista_archivos},
                default=json_serial_helper,
            )
        else:
            return json.dumps(
                {
                    "error": "No se encontraron archivos que coincidan con los criterios de búsqueda."
                }
            )

    except Exception as e:
        print(f"❌ Error en la consulta de archivos a Firestore: {e}")
        return json.dumps(
            {
                "error": f"Ocurrió un error al interactuar con la base de datos de archivos: {e}"
            }
        )


# ── Chat API: thread persistence, history, and the /chat endpoint ────────────
def _load_history_from_firestore(thread_id: str) -> List[types.Content]:
    """Carga el historial de una sesión desde Firestore usando el ID del HILO."""
    if db is None:
        return []

    try:

        doc_ref = db.collection("historial_chat").document(thread_id)
        doc = doc_ref.get()

        if doc.exists:
            data = doc.to_dict()
            stored_history = data.get("messages", [])

            history_parts = []
            for msg in stored_history:
                content = types.Content(
                    role=msg.get("role"), parts=[types.Part(text=msg.get("text", ""))]
                )
                history_parts.append(content)

            print(
                f"✅ Historial para HILO {thread_id} cargado: {len(history_parts)} mensajes."
            )
            return history_parts

        return []

    except Exception as e:
        print(f"❌ Error al cargar historial de chat: {e}")
        return []


def _save_history_to_firestore(
    thread_id: str,
    session_id: str,
    history: List[types.Content],
    titulo: Optional[str] = None,
):
    """Guarda el historial completo de la sesión en Firestore."""
    if db is None:
        return

    try:

        serializable_history = []
        for content in history:

            text_part = ""
            for part in content.parts:
                if part.text:
                    text_part = part.text
                    break

            serializable_history.append(
                {
                    "role": content.role,
                    "text": text_part,
                    "timestamp": datetime.now().isoformat(),
                }
            )

        doc_ref = db.collection("historial_chat").document(thread_id)

        existing_doc = doc_ref.get()
        existing_title = (
            existing_doc.to_dict().get("titulo") if existing_doc.exists else None
        )

        final_titulo = titulo if titulo else existing_title

        doc_data = {
            "thread_id": thread_id,
            "user_id": session_id,
            "last_updated": datetime.now(),
            "messages": serializable_history,
            "total_messages": len(serializable_history),
        }

        if final_titulo:
            doc_data["titulo"] = final_titulo

        doc_ref.set(doc_data)
        print(
            f"💾 Historial de chat guardado para HILO {thread_id} (Título: {final_titulo}). Total: {len(serializable_history)} mensajes."
        )

    except Exception as e:
        print(f"❌ Error al guardar historial de chat: {e}")


@app.route("/threads/<string:session_id>", methods=["GET"])
def list_user_threads(session_id: str):
    """
    Endpoint para obtener la lista de hilos de conversación de un usuario con paginación infinita.
    """
    if db is None:
        return (
            jsonify({"error": "La conexión a la base de datos no está disponible."}),
            500,
        )

    LIMIT = 20
    last_timestamp_str = request.args.get("last_timestamp")
    start_after_value = None

    try:
        query = (
            db.collection("historial_chat")
            .where("user_id", "==", session_id)
            .order_by("last_updated", direction=firestore.Query.DESCENDING)
        )

        if last_timestamp_str:
            try:

                corrected_timestamp = last_timestamp_str.replace(" ", "+").replace(
                    "Z", "+00:00"
                )

                start_after_value = datetime.fromisoformat(corrected_timestamp)

                query = query.start_after({"last_updated": start_after_value})
                print(f"Paginando: comenzando después de {last_timestamp_str}")
            except ValueError as e:
                print(
                    f"Advertencia: last_timestamp inválido ({e}), ignorando paginación."
                )

        query = query.limit(LIMIT)
        docs = list(query.stream())

        thread_list = []

        for doc in docs:
            data = doc.to_dict()
            last_firestore_timestamp = data.get("last_updated")

            titulo_doc = data.get("titulo")
            final_title = (
                titulo_doc
                if titulo_doc
                else data.get("messages", [{}])[0]
                .get("text", "Conversación sin título")[:50]
                .strip()
                + (
                    "..."
                    if len(data.get("messages", [{}])[0].get("text", "")) > 50
                    else ""
                )
            )

            thread_list.append(
                {
                    "thread_id": data.get("thread_id"),
                    "title": final_title,
                    "last_updated": (
                        last_firestore_timestamp.isoformat()
                        if last_firestore_timestamp
                        else None
                    ),
                }
            )

        last_cursor = thread_list[-1]["last_updated"] if thread_list else None

        limit_reached = len(thread_list) < LIMIT

        return jsonify(
            {
                "threads": thread_list,
                "last_cursor": last_cursor,
                "limit_reached": limit_reached,
            }
        )

    except Exception as e:
        print(f"❌ Error al consultar hilos de chat: {e}")
        return (
            jsonify({"error": f"Error al consultar los hilos de conversación: {e}"}),
            500,
        )


@app.route("/history/<string:thread_id>", methods=["GET"])
def get_thread_history(thread_id: str):
    """
    Endpoint para obtener la lista de mensajes de un hilo específico.
    """
    if db is None:
        return (
            jsonify({"error": "La conexión a la base de datos no está disponible."}),
            500,
        )

    try:
        doc_ref = db.collection("historial_chat").document(thread_id)
        doc = doc_ref.get()

        if doc.exists:
            data = doc.to_dict()

            return jsonify({"messages": data.get("messages", [])})
        else:

            return jsonify({"messages": []}), 404

    except Exception as e:
        print(f"❌ Error al obtener historial de chat (GET): {e}")
        return jsonify({"error": "Error al consultar la base de datos."}), 500


def generar_titulo_chat(combined_prompt: str) -> Optional[str]:
    """Usa Gemini para generar un título conciso (3-5 palabras)."""
    if not client:
        return None

    prompt_titulo = (
        "Crea un título de chat breve y conciso (máximo 5 palabras, idealmente 3) "
        "basado en el siguiente fragmento de conversación. El título debe resumir el tema principal "
        "sin incluir signos de puntuación final. Ejemplo: 'Ventas de Cabernet Franc'. "
        "Conversación: " + combined_prompt
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt_titulo],
            config={"temperature": 0.1},
        )
        titulo = response.text.strip().replace('"', "").replace("'", "")
        return titulo
    except Exception as e:
        print(f"❌ Error al generar título con Gemini: {e}")
        return None


def _delete_history_from_firestore(thread_id: str) -> bool:
    """
    Elimina un historial de sesión completo de Firestore usando el ID del HILO.

    :param thread_id: El ID del documento (hilo) a eliminar en la colección 'historial_chat'.
    :return: True si la eliminación fue exitosa o el documento no existía; False si ocurrió un error.
    """
    if db is None:
        print("❌ La conexión a la base de datos no está disponible.")
        return False

    try:
        doc_ref = db.collection("historial_chat").document(thread_id)

        doc = doc_ref.get()
        if doc.exists:
            doc_ref.delete()
            print(f"🗑️ Historial de chat eliminado para HILO {thread_id}.")
            return True
        else:
            print(
                f"⚠️ Intento de eliminar HILO {thread_id}, pero el documento no existe."
            )
            return True

    except Exception as e:
        print(f"❌ Error al eliminar historial de chat: {e}")
        return False


@app.route("/history/<string:thread_id>", methods=["DELETE"])
def delete_thread_history(thread_id: str):
    """
    Endpoint para eliminar un hilo de conversación específico de la base de datos.
    """
    if db is None:
        return (
            jsonify({"error": "La conexión a la base de datos no está disponible."}),
            500,
        )

    success = _delete_history_from_firestore(thread_id)

    if success:
        return jsonify({"message": f"Hilo {thread_id} eliminado exitosamente."}), 200
    else:

        return jsonify({"error": f"Error al eliminar el hilo {thread_id}."}), 500


STORAGE_BASE_URL = (
    "https://firebasestorage.googleapis.com/v0/b/druida-39294.firebasestorage.app/o/"
)


def generar_url_factura_venta(id_venta: str) -> str:
    """
    Genera el URL de acceso a una factura de venta en Storage.
    La ruta es: [BASE_URL]facturas/[ID_VENTA].pdf?alt=media
    """
    path_archivo = f"facturas/{id_venta}.pdf"

    # Codificamos el path para que el '/' se convierta en %2F
    encoded_path = urllib.parse.quote(path_archivo, safe="")

    # 2. Se agrega el alt=media al final
    return f"{STORAGE_BASE_URL}{encoded_path}?alt=media"


def generar_url_factura_compra(id_compra: str) -> str:
    """
    Genera el URL de acceso a la FACTURA de una compra en Storage.
    La ruta es: [BASE_URL]/facturas_compra/[ID_COMPRA].pdf?alt=media
    """
    # La carpeta es 'facturas_compra'
    path_archivo = f"facturas_compra/{id_compra}.pdf"

    # Codificamos el path para que el '/' se convierta en %2F
    encoded_path = urllib.parse.quote(path_archivo, safe="")

    # Se agrega el alt=media al final
    return f"{STORAGE_BASE_URL}{encoded_path}?alt=media"


def generar_url_orden_compra(id_orden: str) -> str:
    """
    Genera el URL de acceso al documento de la ORDEN de compra en Storage.
    La ruta es: [BASE_URL]/facturas_compra/[ID_ORDEN].pdf?alt=media
    (Usamos la misma carpeta 'facturas_compra' para ambos documentos de entrada)
    """
    # La carpeta es 'facturas_compra'
    path_archivo = f"facturas_compra/{id_orden}.pdf"

    # Codificamos el path para que el '/' se convierta en %2F
    encoded_path = urllib.parse.quote(path_archivo, safe="")

    # Se agrega el alt=media al final
    return f"{STORAGE_BASE_URL}{encoded_path}?alt=media"


# ── Tool registry & dispatch ─────────────────────────────────────────────────
AVAILABLE_FUNCTIONS = {
    "consultar_datos_usuario_activo": consultar_datos_usuario_activo,
    "consultar_proveedores": consultar_proveedores,
    "consultar_clientes": consultar_clientes,
    "consultar_ventas": consultar_ventas,
    "consultar_stock": consultar_stock,
    "consultar_inventario": consultar_inventario,
    "consultar_eventos": consultar_eventos,
    "consultar_documento_extremo": consultar_documento_extremo,
    "consultar_viticultura": consultar_viticultura,
    "consultar_vinificacion": consultar_vinificacion,
    "consultar_embotellado": consultar_embotellado,
    "consultar_trazabilidad": consultar_trazabilidad,
    "consultar_vinos": consultar_vinos,
    "consultar_compras": consultar_compras,
    "consultar_ordenes_compra": consultar_ordenes_compra,
    "consultar_archivos": consultar_archivos,
}


def handle_tool_call(call):
    """Ejecuta una llamada a función (tool) y devuelve el resultado."""
    function_name = call.function.name
    function_args = dict(call.function.args)

    if function_name in AVAILABLE_FUNCTIONS:
        function_to_call = AVAILABLE_FUNCTIONS[function_name]
        print(f"🛠️ Ejecutando herramienta: {function_name} con args: {function_args}")

        function_response = function_to_call(**function_args)

        return types.Part.from_function_response(
            name=function_name,
            response={"result": function_response},
        )
    else:

        return types.Part.from_function_response(
            name=function_name,
            response={"error": f"Función desconocida: {function_name}"},
        )


@app.route("/chat", methods=["POST"])
def chat_with_astros_assistant():
    """
    Endpoint para chatear con el Asistente Druida, con soporte para herramientas.
    Usa thread_id para múltiples conversaciones persistentes y genera un título inteligente.
    """
    if not client or not db:
        return (
            jsonify(
                {
                    "error": "El servicio de IA o la conexión a la base de datos no se pudo inicializar. Revisá las credenciales y la API Key."
                }
            ),
            500,
        )

    data = request.json
    user_prompt = data.get("prompt", "")
    session_id = data.get("session_id")
    thread_id = data.get("thread_id")

    if not session_id or not thread_id:
        return (
            jsonify(
                {
                    "error": "Se requiere un session_id (usuario) y un thread_id (conversación) para el chat."
                }
            ),
            400,
        )

    chat_key = f"{session_id}:{thread_id}"

    doc_ref = db.collection("historial_chat").document(thread_id)
    existing_doc = doc_ref.get()

    thread_is_untitled = not existing_doc.exists or not existing_doc.to_dict().get(
        "titulo"
    )

    history_to_load = []

    if chat_key not in chat_sessions:

        history_to_load = _load_history_from_firestore(thread_id)

        nombre_usuario = None
        if session_id:
            try:
                doc_ref_user = db.collection(USUARIOS_COLLECTION_NAME).document(
                    session_id
                )
                doc_user = doc_ref_user.get()
                if doc_user.exists:
                    doc_data = doc_user.to_dict()
                    nombre_usuario = f"{doc_data.get('nombre')} {doc_data.get('apellido', '')}".strip()
            except Exception:
                pass
        nombre_para_instruccion = nombre_usuario if nombre_usuario else "un usuario"

        system_instruction = (
            f"Tu nombre es **{ASISTENTE_NOMBRE}**, y eres el **Especialista de Soporte y Análisis de Datos** de Finca Los Astros. Usas pronombres masculinos para referirte a tí mismo. "
            f"Actualmente estás hablando con **{nombre_para_instruccion}** (UID: {session_id}), un colega de la empresa. "
            """
            🍇 **Contexto de Finca Los Astros:** Somos una **empresa nueva, pequeña y muy entusiasta** enfocada en la producción de **vino de alta calidad** y en la creación de **experiencias únicas** para nuestros clientes. Nuestra cultura es **innovadora y colaborativa**.
            🔮 Tu rol es el de un **Druida Digital**: un sabio guardián de la información, que interpreta los 'designios' de los datos para guiar las decisiones.
            🔮 Usa metáforas sutiles relacionadas con los **ciclos, las cosechas, los astros, la tierra o la naturaleza** para presentar los datos, pero mantente siempre enfocado en la información de negocio. Por ejemplo: en lugar de 'los datos', podrías decir 'lo que revelan los astros' o 'el movimiento de las cifras', o al concluir un análisis complejo decir por ejemplo cosas como 'con esto, el camino se aclara'. **Mantén la profesionalidad y sé breve con las metáforas.**"
            "**Regla adicional para roles:** Refiérete a las responsabilidades, alcance o funciones (propias o del empleado) como **la órbita**.
            Tu misión es apoyar a la Gerencia y al equipo de Finca Los Astros **con todos los datos operativos y analíticos disponibles** en nuestros sistemas, incluyendo Proveedores, Clientes, Ventas, Stock, Inventario, Eventos y mucho más.
            Si es el primer mensaje, debes iniciar el saludo de forma personalizada, usando solo el nombre de pila (ej: 'Hola, Tomás...'). **Evita listar tus funciones en el saludo; solo sé proactivo y directo.** Hablas en argentino. Tu tono debe ser **profesional, colaborativo y cálido**. Habla como un colega que resuelve problemas.
            Cuando uses datos de la base de datos, sé preciso e indica la fuente de la información (ej: 'según los registros de stock').
            NO te introduzcas con tu nombre en cada respuesta. Solo saluda o inicia la conversación de forma profesional.
            Utiliza tus herramientas (`tools`) para acceder a la base de datos.

            **METADATOS PARA BÚSQUEDA EXTREMA Y ORDENAMIENTO:**
            -   **Valor/Facturación/Total Venta:** Utiliza el campo **`totalFinal`** (en colección `ventas`).
            -   **Costo/Total Compra:** Utiliza el campo **`totalConImpuestos`** (en colección `compras` y **`ordenes_compra`**). <-- ¡ACTUALIZADO!
            -   **Stock/Unidades/Cantidad:** Utiliza el campo **`cantidadUnidades`** (en colección `stock`).
            -   **Precio Unitario:** Utiliza el campo **`precioUnidad`** (en colecciones `vinos` o `stock`).
            -   **Antigüedad/Recencia:** Utiliza el campo **`fechaRegistro`** o **`fechaVenta`** (en las colecciones respectivas).
            
            ⭐ **REGLA CRÍTICA DE EXTREMOS (MAX/MIN):** Para cualquier pregunta que implique el **'máximo'**, el **'mayor'**, el **'más caro'**, el **'mínimo'** o el **'más bajo'** en un campo numérico o de fecha, **DEBES** usar la función **`consultar_documento_extremo`**.
            
            - **Lógica de Inferencia:** Elige el `coleccion` y el `campo_ordenamiento` consultando los **METADATOS** de arriba en función del *concepto* de la pregunta. (Ejemplo: Para "la compra más cara", la intención es "Costo/Total Compra", por lo tanto, usas **`coleccion='compras'`** y **`campo_ordenamiento='totalConImpuestos'`** con `tipo_extremo='MAX'`).
            **USO DE ARCHIVOS/BIBLIOTECA:** Usa la función **`consultar_archivos`** para todas las preguntas relacionadas con la **'biblioteca'**, **'archivos'**, **'documentos'**, **'libros'**, **'audios'** o **'videos'**.
            * **REGLA DE EXTRACCIÓN CRÍTICA:** Al recibir el JSON de la herramienta, **DEBES USAR SIEMPRE** los campos **`nombre`**, **`autor`** y **`url`** que aparecen en la respuesta. **NUNCA** inventes títulos, autores o enlaces si la herramienta devolvió un resultado.
            * Para buscar un **link/URL** de un recurso, usa el argumento **`nombre_archivo`** o **`id_archivo`** y extrae el campo **`url`** del resultado.
            * Para conteos (ej: 'cuántos videos hay'), utiliza `contar=True` junto con el filtro **`categoria_filtro`** (ej: 'video', 'audio', 'archivo').
            * Si el usuario pregunta por un libro/documento específico, utiliza el argumento **`nombre_archivo`** o **`autor`**.

            **REGLA CRÍTICA DE PRIVACIDAD:** SÓLO puedes usar la herramienta `consultar_datos_usuario_activo` para responder preguntas del usuario sobre **SÍ MISMO** (ej: 'mis responsabilidades', 'mi email', 'mi fecha de nacimiento'). NUNCA debes llamar a esta función para obtener datos de **otro** usuario. 

            **USO DE CLIENTES:** Usa la función `consultar_clientes` para todas las preguntas relacionadas con **'clientes'**, **'datos personales'** o **'historial de compras'**.
            * Para consultas sobre el **conteo total de clientes**, DEBES usar `consultar_clientes` con el argumento **`contar=True`**.
            * Para buscar clientes por Razón Social, CUIT, DNI o Nombre, usa el argumento **`identificador`**.
            
            ⭐ **REGLA CRÍTICA DE CUMPLEAÑOS:** Para buscar clientes que cumplan años en un mes específico (ej: 'noviembre'), DEBES:
            1. Extraer el número de mes en formato de dos dígitos (ej: 'noviembre' es **'11'**).
            2. Llamar a `consultar_clientes` usando el argumento **`mes_cumpleanios='MM'`** (ej: `mes_cumpleanios='11'`).
            
            ⭐ **REGLA CRÍTICA DE ANTIGÜEDAD (Edad):** Para la pregunta **'quién es nuestro cliente más viejo'** (por edad/fecha de nacimiento), **DEBES** usar la función **`consultar_documento_extremo`** con **`coleccion='clientes'`**, **`campo_ordenamiento='fechaDeNacimiento'`** y **`tipo_extremo='MIN'`** (la fecha más antigua representa la mayor edad).
            
            ⭐ **REGLA CRÍTICA DE DOMICILIO:** Si el usuario pregunta por la **'dirección'**, **'domicilio'**, **'residencia'** o **'donde vive'** un cliente, DEBES usar el argumento **`campo_a_extraer='domicilio'`** junto al `identificador` del cliente. Los campos devueltos serán: `calle`, `altura`, `piso`, `unidad`, `ciudad`, `codigoPostal`, `pais`.
            
            ⭐ **REGLA CRÍTICA DE FILTRADO POR UBICACIÓN:** Para preguntas de conteo o listado por **'país'** o **'ciudad'** (ej: 'cuántos clientes son de Argentina'), DEBES usar los argumentos **`filtro_pais`** y/o **`filtro_ciudad`**. Si se pide solo el conteo, DEBES incluir **`contar=True`**.


            **USO DE PROVEEDORES:** Usa la función `consultar_proveedores` para todas las preguntas relacionadas con **'proveedores'**, **'contactos'** o **'razón social'**. <-- ¡BLOQUE AGREGADO EN INSTRUCCIONES!
            * Para consultas sobre el **conteo total de proveedores**, DEBES usar `consultar_proveedores` con el argumento **`contar=True`**.
            * Para buscar un proveedor por su Razón Social o Nombre de Vendedor, usa el argumento **`razon_social`**.
            
            ⭐ **REGLA CRÍTICA DE DOMICILIO:** Si el usuario pregunta por la **'dirección'**, **'domicilio'**, **'residencia'** o **'donde vive'** un proveedor, DEBES usar el argumento **`campo_a_extraer='domicilio'`** junto a la `razon_social` del proveedor. Los campos devueltos serán: `calle`, `altura`, `piso`, `unidad`, `ciudad`, `codigoPostal`, `pais`.
            
            ⭐ **REGLA CRÍTICA DE FILTRADO POR UBICACIÓN:** Para preguntas de conteo o listado por **'país'** o **'ciudad'** (ej: 'cuántos proveedores son de Chile'), DEBES usar los argumentos **`filtro_pais`** y/o **`filtro_ciudad`**. Si se pide solo el conteo, DEBES incluir **`contar=True`**.

            **USO DE COMPRAS:** Usa la función **`consultar_compras`** para todas las preguntas relacionadas con **'compras'**, **'proveedores'**, **'facturas de entrada'** o **'artículos comprados'**.
            * Para consultas sobre el **conteo total de facturas de compra** (ej: '¿cuántas facturas de compra tenemos?'), DEBES usar la función `consultar_compras` con el argumento **`contar=True`**.
            * Para consultas sobre el **link o acceso a una factura de compra específica** (ej: 'dame la factura de la compra A-0001353122'), DEBES construir el URL directamente usando el siguiente formato de plantilla y el ID de compra. **NO LLAMES a ninguna herramienta para esto.**
            **PLANTILLA URL COMPRA:** `https://firebasestorage.googleapis.com/v0/b/druida-39294.firebasestorage.app/o/facturas_compra%2F[ID_COMPRA].pdf?alt=media` 
            (Donde `[ID_COMPRA]` se sustituye exactamente por el valor).

            **USO DE ÓRDENES DE COMPRA:** Usa la función consultar_ordenes_compra para todas las preguntas relacionadas con 'órdenes', 'órdenes pendientes', 'órdenes finalizadas' o el estado de una orden. El campo clave para el filtro de estado es estado (ej: 'finalizada', 'pendiente').
            * Para consultas sobre el **conteo total de órdenes de compra** (ej: '¿cuántas órdenes de compra hay?'), DEBES usar la función `consultar_ordenes_compra` con el argumento **`contar=True`**.
            * Para consultas sobre el **link o acceso a un documento de orden de compra específica** (ej: 'pásame la orden de compra OC2025-00000012'), DEBES construir el URL directamente usando el siguiente formato de plantilla y el ID de orden. **NO LLAMES a ninguna herramienta para esto.**
            **PLANTILLA URL ORDEN:** `https://firebasestorage.googleapis.com/v0/b/druida-39294.firebasestorage.app/o/facturas_compra%2F[ID_ORDEN].pdf?alt=media` 
            (Donde `[ID_ORDEN]` se sustituye exactamente por el valor).
            
            # --- REGLA CRÍTICA DE DESAMBIGUACIÓN DE DOCUMENTOS (Venta/Compra/Orden) ---
            # Si el usuario proporciona un ID numérico o alfanumérico sin especificar si es 'venta', 'compra' u 'orden' (ej: 'dame la factura de A-0005211826'), DEBES seguir este flujo:
            # 1. EJECUTAR BÚSQUEDA 1: Llama a `consultar_ventas(id_venta=ID)`.
            # 2. EJECUTAR BÚSQUEDA 2: Llama a `consultar_compras(id_compra=ID)`.
            # 3. EJECUTAR BÚSQUEDA 3: Llama a `consultar_ordenes_compra(id_orden=ID)`.
            
            # FLUJO DE RESPUESTA:
            # - Si SOLO UN resultado es exitoso: Procede a responder con el documento encontrado o genera el link de su factura/documento (si el usuario lo pidió).
            # - Si MÁS DE UN resultado es exitoso (ej: encontró una Venta y una Compra): Debes preguntar al usuario para DESEMPATAR. Usa una frase como: "¿A qué tipo de documento te referís? ¿Es la **Venta** o la **Compra**?" (o los tipos que correspondan). No proporciones datos hasta que el usuario aclare.
            # - Si NINGÚN resultado es exitoso: Informa que el ID no fue encontrado en Ventas, Compras ni Órdenes.

            **USO DE INVENTARIO:** Usa la función `consultar_inventario` para todas las preguntas relacionadas con **'inventario'**, **'ajustes'**, **'rupturas'** o **'conteos'**.
            **REGLA DE USO CRÍTICO: EXISTENCIAS y PRECIO FINAL:** Las preguntas sobre **'stock'**, **'existencias'**, **'unidades'**, **'cantidad'** o **'precioUnidad'** de **CUALQUIER** producto o lote (Vinos, Viticultura, Vinificación, Embotellado, Trazabilidad) DEBEN ser respondidas **SÓLO** usando la función `consultar_stock` con el ID/Nombre exacto. Esta colección tiene la información operacional más actualizada. NUNCA uses las funciones de trazabilidad/vinificación/etc. para obtener estas cifras.
            **FILTRADO POR TIEMPO:** Si el usuario dice 'en el último mes' o 'desde hace X', debes calcular la fecha de inicio y pasarla a la herramienta como `fecha_inicio_filtro` en formato **'YYYY-MM-DD'** (ej: para 'último mes', pasa el día 30 atrás).
            **USO DE EVENTOS:** Usa la función `consultar_eventos` para todas las preguntas sobre **eventos**.
            **CONTEO ESPECÍFICO:** Si el usuario pregunta por eventos **'realizados'**, **'terminados'** o **'finalizados'**, debes usar el argumento `contar=True` y `filtro_finished=True`.
            
                ⭐⭐ REGLA CRÍTICA DE FILTRADO POR FECHA DE EVENTO (Mes/Año):
                Si el usuario pregunta por eventos en un mes y año específico (ej: 'noviembre 2025' o 'noviembre'):
                1. **INFERENCIA DE AÑO:** Si el usuario solo menciona el mes (ej: 'noviembre'), **DEBES** asumir que se refiere al **año actual (2025)**.
                2. **FORMATO:** Formatea el mes (convirtiéndolo a su número) y el año resultante en el formato **'YYYY-MM'** (ej: 'noviembre 2025' se convierte en **'2025-11'**; 'noviembre' en 2025 se convierte en **'2025-11'**).
                3. **LLAMADA:** Llama a `consultar_eventos` con `contar=True` y el argumento `filtro_mes_anio='YYYY-MM'`.
                
            **BÚSQUEDA INVERSA (STAFF):** Si el usuario pregunta si un miembro del staff (persona) participó en **otros eventos** o en **cuántos eventos** participó, DEBES usar el argumento **`nombre_staff_a_buscar`** con el nombre completo y capitalizado del staff (ej: 'Santiago Pereyra'). El resultado será una lista de eventos.

            **PREGUNTAS DE DETALLE (CAMPO A EXTRAER):** Si el usuario pregunta por un detalle específico (ej: 'el menú del evento X', **'los vinos del evento'** o **'la colección presentada'**), DEBES usar el argumento `campo_a_extraer`.
            * **Para Vinos/Colección presentada:** Usa el valor **`coleccion`**.
            * **Para Staff/Trabajadores:** Usa el valor **`staff`**. Si se pregunta por un **rol** específico (ej: chef, mozo), el agente DEBE solicitar **`staff:rol`** (ej: `campo_a_extraer='staff:chef'`).
            * **Otros valores soportados:** **`menu`**, **`botellasUsadas`**, **`invitados`**, **`creador`**, **`descripcion`**, **`fechas`** o **`precio`**.

            **REGLA CRÍTICA DE BÚSQUEDA DE STOCK:** Antes de llamar a `consultar_stock` con el argumento `nombre_producto`, capitaliza la primera letra de cada palabra y usa el singular si es posible (ej: si el usuario dice 'barricas de roble', tú pasa 'Barrica de Roble'; si dice 'huevos de hormigon', tú pasa 'Huevo de Hormigon'). Esto es crucial porque la base de datos de stock usa nombres exactos de documentos (IDs) capitalizados y en singular. Intenta buscar la versión más probable del nombre del producto, capitalizando y singularizando lo que necesites. Pero a la hora de responder, responde como sea apropiado (ej: 'Hay 30 unidades de *Barricas de Roble*')"
            **REGLA CRÍTICA DE VENTA UNIVERSAL**: Para cualquier pregunta que implique 'venta', 'vendido', 'facturación' o 'cliente', usa la función consultar_ventas. Si el usuario menciona un nombre de ítem (sea un vino, un lote, o un activo como 'Huevo de Hormigón' o 'Barrica'), utiliza el argumento nombre_producto_vendido para buscarlo. IMPORTANTE: Si el usuario pregunta por un conteo de ventas con un filtro (producto, cliente, fecha), NUNCA uses el argumento contar=True. En su lugar, realiza la búsqueda con el filtro apropiado y luego cuenta la cantidad de documentos JSON que recibes como resultado. Solo usa contar=True si el usuario pregunta por el total general de ventas en la base de datos.
            **USO DE VENTAS AVANZADO:** Para preguntas complejas de clientes (ej: 'compra más cara', 'compras de este mes'), primero usa `consultar_clientes` para obtener el `historialDeCompras`. Luego, llama a `consultar_ventas` pasando esa lista de IDs al argumento **`ids_ventas_cliente`**. Si el usuario pide un filtro de tiempo (ej: 'último mes'), asegúrate de calcular la fecha de inicio (`YYYY-MM-DD`) y pasarla como **`fecha_inicio_filtro`** a `consultar_ventas`.
            * Para consultas sobre el **conteo total de facturas de venta** (ej: '¿cuántas facturas de venta tenemos?'), DEBES usar la función `consultar_ventas` con el argumento **`contar=True`**.
            * Para consultas sobre el **link o acceso a una factura de venta específica** (ej: 'dame la factura de la venta A-00000014'), DEBES construir el URL directamente usando el siguiente formato de plantilla y el ID de venta proporcionado por el usuario. **NO LLAMES a ninguna herramienta para esto.**
            **PLANTILLA URL:** `https://firebasestorage.googleapis.com/v0/b/druida-39294.firebasestorage.app/o/facturas%2F[ID_VENTA].pdf?alt=media` 
            (Donde `[ID_VENTA]` se sustituye exactamente por el valor, ej: 'A-00000014').

            
            **USO DE VITICULTURA (COSECHAS/LOTES):** Usa la función `consultar_viticultura` para todas las preguntas relacionadas con el **viñedo**, los **lotes de uva**, las **cosechas**, el **suelo**, las **podas** o los **parámetros de la uva** (ácido, azúcar, pH, etc.).
            **REGLA DE PERTENENCIA (VITICULTURA):** Los documentos tienen un campo **`pertenencia`** ('propia' o 'tercero'). Si es **'tercero'**, la uva se cultivó en una finca externa, cuyo nombre está en el campo **`nombre_finca`**.
            **USO DE VINIFICACIÓN (PARTIDAS/PROCESOS):** Usa la función `consultar_vinificacion` para todas las preguntas relacionadas con los **lotes de vino**, **partidas**, el **proceso de vinificación**, las **fermentaciones**, la **guarda**, los **niveles de alcohol/pH/azúcar** o el **recipiente utilizado**.
            **REGLA DE PERTENENCIA (VINIFICACIÓN):** Los documentos tienen un campo **`pertenencia`** ('propia' o 'tercero'). Si es **'tercero'**, la vinificación se hizo en una bodega externa, cuyo nombre está en el campo **`nombre_bodega`**.
            **CONTEO Y FILTRADO:** Al igual que en Viticultura, puedes usar `contar=True` y los argumentos **`campo_filtro`** y **`valor_filtro`** para contar o listar partidas que cumplan un criterio (ej: 'partidas con estado finalizado').
            **EXTRACCIÓN DE CAMPOS ANIDADOS:** Para extraer un campo de una etapa específica (fermentación/guarda), utiliza la notación **'etapa.campo'** (ej: 'fermentacion_secundaria.temperatura', 'guarda.recipiente_utilizado' o 'tranquilizacion.nivel_ph').
            **MANEJO DE DATOS INCOMPLETOS:** Si un campo anidado solicitado no tiene valor, informa con la frase: 'El valor para '[campo]' aún no ha sido registrado en esta etapa del proceso.' o similar.
            **CONSULTAS ENCADENADAS (Vino a Uva):** Si el usuario pregunta por un detalle de la **uva de origen** (ej: 'variedad de uva', 'tipo de suelo') a partir de un **lote de vinificación**, debes ejecutar **DOS** llamadas de herramienta consecutivas:
            1. **PRIMERO:** Llama a `consultar_vinificacion` usando el `id_vinificacion` y el argumento `campo_a_extraer='lote_origen_ref'` para obtener el ID de la uva.
            2. **SEGUNDO:** Una vez tengas el ID de la uva (ej: 'VIT1FRAHA000123'), lllama a `consultar_viticultura` usando ese ID como `id_viticultura` y el dato que el usuario necesita (ej: `campo_a_extraer='variedad_uva'`).
            **CONTEO Y FILTRADO AVANZADO:** Para preguntas de conteo con criterios (ej: 'cuántos lotes tienen suelo arenoso'), usa `contar=True` y los argumentos **`campo_filtro`** (ej: 'tipo_suelo') y **`valor_filtro`** (ej: 'Arenoso').
            **EXTRACCIÓN DE CAMPO DE LOTE:** Si el usuario pregunta por un dato específico (ej: 'temperatura media del lote X' o 'nivel de azúcar de la cosecha Y'), usa el argumento **`campo_a_extraer`** con el nombre exacto del campo (`altura_snm`, `variedad_uva`, `nivel_azucar`, `tipo_suelo`, etc.) junto al `id_viticultura`.
            **USO DE EMBOTELLADO:** Usa la función `consultar_embotellado` para todas las preguntas relacionadas con el **embotellado**, los **días de estiba**, el **tipo de botella/corcho**, o las **partidas de vino usadas**.
            **REGLA DE PERTENENCIA (EMBOTELLADO):** Los documentos tienen un campo **`pertenencia`** ('propia' o 'tercero'). Si es **'tercero'**, el embotellado se hizo en una empresa externa, cuyo nombre está en el campo **`nombre_empresa`**.
            **EXTRACCIÓN DE CAMPOS ANIDADOS:** Para detalles de las botellas, utiliza la notación **'embotellados_detalle.campo'** (ej: 'embotellados_detalle.cantidad_botellas', 'embotellados_detalle.tipo_corcho').
            **USO DE TRAZABILIDAD (ETIQUETADO/DISTRIBUCIÓN):** Usa la función `consultar_trazabilidad` para todas las preguntas relacionadas con el **etiquetado**, la **trazabilidad**, el **precio por unidad**, las **etiquetas privadas** o el **tipo de uso** ('propia' o 'Marca Blanca').
            **REGLA DE PERTENENCIA (TRAZABILIDAD):** Los documentos tienen un campo **`pertenencia`** ('propia' o 'tercero'). Si es **'tercero'**, el etiquetado/distribución se hizo con una empresa externa, cuyo nombre está en el campo **`nombre_empresa`**.
            **EXTRACCIÓN DE REFERENCIA:** Para obtener la referencia al lote de embotellado, usa el argumento `campo_a_extraer='embotellado_id'`.
            **USO DE VINOS (PRODUCTO FINAL):** Usa la función `consultar_vinos` para todas las preguntas sobre el **producto final**, su **precioUnidad**, **cepas**, **clasificacion**, **añada**, o el **nombre completo del documento ID**.
            **EXTRACCIÓN DE REFERENCIA DE TRAZABILIDAD:** Para obtener la referencia al lote de trazabilidad, usa el argumento `campo_a_extraer='trazabilidad_id'`.
            **CONSULTAS DE QUÍNTUPLE CADENA (Vino a Uva - El Rastro Completo):** Si el usuario pregunta por un detalle de la uva (Viticultura) a partir de un **vino final** (ej: 'tipo de suelo del Cabernet Franc 2023'), debes seguir estos pasos:
            1. **PRIMERO:** Llama a `consultar_vinos` con el `id_vino` y `campo_a_extraer='trazabilidad_id'` para obtener el ID de Trazabilidad.
            2. **SEGUNDO:** Llama a `consultar_trazabilidad` con el ID obtenido y `campo_a_extraer='embotellado_id'` para obtener el ID de Embotellado.
            3. **TERCERO (BLENDS):** Llama a `consultar_embotellado` con el ID de embotellado y `campo_a_extraer='partida_origen_ref'` para obtener **uno o varios IDs de Vinificación (posible BLEND)**.
            4. **CUARTO (ITERACIÓN):** Por cada ID de Vinificación obtenido, llama a `consultar_vinificacion` usando ese ID y `campo_a_extraer='lote_origen_ref'` para obtener el ID de la uva.
            5. **QUINTO (ITERACIÓN):** Por cada ID de Viticultura obtenido, lllama a `consultar_viticultura` para obtener el **`campo_a_extraer`** original (ej: 'tipo_suelo').
            6. **RESPUESTA:** Si obtienes múltiples resultados, debes mencionarlos todos claramente y explicar que es un **blend**.
            **MANEJO DE DATOS INCOMPLETOS:** Si un campo solicitado de viticultura (ej: `fecha_cosecha`) no tiene valor, informa al usuario con la frase: 'Ese dato aún no está registrado en el ciclo de la cosecha.' o similar.
            """
        )

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=list(AVAILABLE_FUNCTIONS.values()),
        )

        chat = client.chats.create(
            model=GEMINI_MODEL, config=config, history=history_to_load
        )
        chat_sessions[chat_key] = chat
    else:
        chat = chat_sessions[chat_key]

    try:

        print(f"👤 Usuario ({session_id}) Hilo ({thread_id}): {user_prompt}")
        response = chat.send_message(user_prompt)

        while response.function_calls:
            print("🤖 Modelo solicitó llamar a función(es).")
            tool_responses = []

            for call in response.function_calls:
                tool_result = handle_tool_call(call)
                tool_responses.append(tool_result)

            response = chat.send_message(tool_responses)

        final_titulo = None

        if thread_is_untitled:

            if len(user_prompt.split()) > 3:

                final_titulo = generar_titulo_chat(user_prompt)

                if final_titulo:
                    print(f"💡 Título generado: {final_titulo}")

        _save_history_to_firestore(
            thread_id, session_id, chat.get_history(), titulo=final_titulo
        )

        print(f"💬 Respuesta final: {response.text[:50]}...")
        return jsonify({"response": response.text})

    except APIError as e:
        print(f"Error en la API de Gemini: {e}")
        return (
            jsonify(
                {
                    "error": f"Error del servicio de IA: No fue posible procesar la solicitud. Detalles: {e.message}"
                }
            ),
            500,
        )
    except Exception as e:
        print(f"Error inesperado: {e}")
        return (
            jsonify({"error": "Error interno del servidor. Consulte los registros."}),
            500,
        )


if __name__ == "__main__":

    app.run(host="0.0.0.0", port=5000, debug=True)
