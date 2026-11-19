# -*- coding: utf-8 -*-
"""Firestore NoSQL Database Client & In-Memory Document Store Simulator
Provides real Google Cloud Firestore integration and thread-safe in-memory NoSQL engine.
"""

import os
import time
import logging
import threading
from typing import Dict, Any, List, Optional

logger = logging.getLogger("FirestoreClient")

try:
    from google.cloud import firestore
    HAS_FIRESTORE = True
except ImportError:
    HAS_FIRESTORE = False


class InMemoryDocumentReference:
    def __init__(self, collection_name: str, doc_id: str, store: "InMemoryFirestore"):
        self.collection_name = collection_name
        self.id = doc_id
        self.store = store

    def set(self, data: Dict[str, Any], merge: bool = False):
        self.store._set_doc(self.collection_name, self.id, data, merge=merge)

    def get(self) -> "InMemoryDocumentSnapshot":
        data = self.store._get_doc(self.collection_name, self.id)
        return InMemoryDocumentSnapshot(self.id, data)

    def delete(self):
        self.store._delete_doc(self.collection_name, self.id)


class InMemoryDocumentSnapshot:
    def __init__(self, doc_id: str, data: Optional[Dict[str, Any]]):
        self.id = doc_id
        self._data = data
        self.exists = data is not None

    def to_dict(self) -> Optional[Dict[str, Any]]:
        return dict(self._data) if self._data else None


class InMemoryCollectionReference:
    def __init__(self, collection_name: str, store: "InMemoryFirestore"):
        self.collection_name = collection_name
        self.store = store

    def document(self, doc_id: str) -> InMemoryDocumentReference:
        return InMemoryDocumentReference(self.collection_name, doc_id, self.store)

    def stream(self) -> List[InMemoryDocumentSnapshot]:
        return self.store._stream_collection(self.collection_name)

    def where(self, field: str, op: str, value: Any) -> "InMemoryQuery":
        return InMemoryQuery(self.collection_name, self.store, [(field, op, value)])


class InMemoryQuery:
    def __init__(self, collection_name: str, store: "InMemoryFirestore", filters: list):
        self.collection_name = collection_name
        self.store = store
        self.filters = filters

    def where(self, field: str, op: str, value: Any) -> "InMemoryQuery":
        self.filters.append((field, op, value))
        return self

    def stream(self) -> List[InMemoryDocumentSnapshot]:
        snapshots = self.store._stream_collection(self.collection_name)
        matched = []
        for snap in snapshots:
            d = snap.to_dict() or {}
            match = True
            for field, op, val in self.filters:
                doc_val = d.get(field)
                if op == "==" and doc_val != val:
                    match = False; break
                elif op == ">" and (doc_val is None or doc_val <= val):
                    match = False; break
                elif op == "<" and (doc_val is None or doc_val >= val):
                    match = False; break
                elif op == ">=" and (doc_val is None or doc_val < val):
                    match = False; break
                elif op == "<=" and (doc_val is None or doc_val > val):
                    match = False; break
            if match:
                matched.append(snap)
        return matched


class InMemoryFirestore:
    """Thread-safe in-memory document store matching Firestore API."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(InMemoryFirestore, cls).__new__(cls)
                cls._instance._init_store()
            return cls._instance

    def _init_store(self):
        self.collections: Dict[str, Dict[str, Dict[str, Any]]] = {
            "realtime_bus_estimates": {},
            "passenger_demand": {},
            "delay_alerts": {}
        }
        self.lock = threading.RLock()

    def reset(self):
        with self.lock:
            self._init_store()

    def collection(self, name: str) -> InMemoryCollectionReference:
        with self.lock:
            if name not in self.collections:
                self.collections[name] = {}
        return InMemoryCollectionReference(name, self)

    def _set_doc(self, collection: str, doc_id: str, data: Dict[str, Any], merge: bool = False):
        with self.lock:
            if collection not in self.collections:
                self.collections[collection] = {}
            if merge and doc_id in self.collections[collection]:
                self.collections[collection][doc_id].update(data)
            else:
                self.collections[collection][doc_id] = dict(data)

    def _get_doc(self, collection: str, doc_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            col = self.collections.get(collection, {})
            return col.get(doc_id)

    def _delete_doc(self, collection: str, doc_id: str):
        with self.lock:
            col = self.collections.get(collection, {})
            if doc_id in col:
                del col[doc_id]

    def _stream_collection(self, collection: str) -> List[InMemoryDocumentSnapshot]:
        with self.lock:
            col = self.collections.get(collection, {})
            return [InMemoryDocumentSnapshot(doc_id, dict(data)) for doc_id, data in col.items()]


class SafeDocumentReference:
    def __init__(self, real_doc, mem_doc):
        self.real_doc = real_doc
        self.mem_doc = mem_doc

    def set(self, data: Dict[str, Any], merge: bool = False):
        if self.mem_doc:
            try:
                self.mem_doc.set(data, merge=merge)
            except Exception as e:
                logger.warning(f"Error setting in-memory document: {e}")
        if self.real_doc:
            try:
                self.real_doc.set(data, merge=merge)
            except Exception as e:
                logger.warning(f"Cloud Firestore set failed (using in-memory fallback): {e}")

    def get(self):
        if self.real_doc:
            try:
                snap = self.real_doc.get()
                if snap.exists:
                    return snap
            except Exception:
                pass
        return self.mem_doc.get() if self.mem_doc else None

    def delete(self):
        if self.mem_doc:
            try:
                self.mem_doc.delete()
            except Exception:
                pass
        if self.real_doc:
            try:
                self.real_doc.delete()
            except Exception:
                pass

    def __getattr__(self, name):
        if self.real_doc:
            return getattr(self.real_doc, name)
        return getattr(self.mem_doc, name)


class SafeCollectionWrapper:
    def __init__(self, collection_name: str, real_col, mem_col):
        self.collection_name = collection_name
        self.real_col = real_col
        self.mem_col = mem_col

    def stream(self):
        docs = []
        if self.real_col:
            try:
                docs = list(self.real_col.stream())
            except Exception as e:
                logger.warning(f"Cloud Firestore stream failed (using in-memory fallback): {e}")
                docs = []
        if not docs and self.mem_col:
            docs = self.mem_col.stream()
        return docs

    def document(self, doc_id: str):
        real_doc = self.real_col.document(doc_id) if self.real_col else None
        mem_doc = self.mem_col.document(doc_id) if self.mem_col else None
        return SafeDocumentReference(real_doc, mem_doc)

    def where(self, *args, **kwargs):
        if self.real_col:
            try:
                return self.real_col.where(*args, **kwargs)
            except Exception:
                pass
        return self.mem_col.where(*args, **kwargs) if self.mem_col else None

    def __getattr__(self, name):
        if self.real_col:
            return getattr(self.real_col, name)
        return getattr(self.mem_col, name)


class TransitFirestoreClient:
    """Unified Firestore NoSQL Client."""

    def __init__(self, project_id: Optional[str] = None):
        proj = project_id or os.environ.get("GCP_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("PROJECT_ID")
        if not proj or proj == "transit-s11-prod":
            proj = "transit-s11-bits-12730"
        self.project_id = proj
        self.real_client = None
        self.in_memory = InMemoryFirestore()

        if HAS_FIRESTORE and self.project_id:
            try:
                self.real_client = firestore.Client(project=self.project_id)
                logger.info(f"[✓] Connected to Google Cloud Firestore (Project: {self.project_id})")
            except Exception as e:
                logger.warning(f"Could not connect to live Firestore: {e}. Using in-memory NoSQL engine.")
                self.real_client = None

    def collection(self, name: str):
        mem_col = self.in_memory.collection(name)
        if self.real_client:
            return SafeCollectionWrapper(name, self.real_client.collection(name), mem_col)
        return mem_col

