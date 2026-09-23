"""Callable recipe for a later sealed cell; authoring only, not executed here."""
import pickle


def run(history, emit):
    from django.core.files.base import ContentFile
    from django.db import connection
    from m003_s10_django_fixture.models import Document

    if history not in ("control", "trigger"):
        raise ValueError("Invalid history")
    # Parent configures the registered app and a new cell-owned SQLite database.
    with connection.schema_editor() as editor:
        editor.create_model(Document)
    document = Document(pk=1, myfile="test_file.py")
    document.myfile.save("test_file.py", ContentFile(b"M003 S10 rank79 file\n"))
    original = document.myfile
    emit("FIXTURE_READY", {"pk": document.pk, "name": original.name})
    assert document.pk == 1 and original.name == "unused/test_file.py"
    assert original.url == "/s10-media/unused/test_file.py"
    emit("REFERENCE_CAPTURED", {"name": original.name, "url": original.url})

    emit("SERIALIZE_ENTER", {"pickle_protocol": 4})
    payload = pickle.dumps(document if history == "control" else original, protocol=4)
    emit("SERIALIZE_RETURN", {"bytes": len(payload)})
    emit("RESTORE_ENTER", {})
    restored_object = pickle.loads(payload)
    emit("RESTORE_RETURN", {})
    # Only the lawful whole-model history uses a descriptor after restoration.
    restored = restored_object.myfile if history == "control" else restored_object
    emit("FILE_SELECTED", {"file_type": type(restored).__module__ + "." + type(restored).__qualname__})
    checks = {}
    witnesses = {}
    for attribute in ("file_equal", "name", "url", "storage", "instance", "field"):
        try:
            left = original if attribute == "file_equal" else getattr(original, attribute)
            right = restored if attribute == "file_equal" else getattr(restored, attribute)
            equal = left == right
            if type(equal) is not bool:
                raise TypeError("Native equality did not return bool")
            check = {"status": "VALUE", "equal": equal, "error": None}
            if attribute in ("name", "url"):
                witnesses[attribute] = right
            elif attribute == "instance":
                witnesses["instance_key"] = {"model_label": right._meta.label, "pk": right.pk}
            elif attribute == "field":
                witnesses["field_key"] = {"model_label": right.model._meta.label, "name": right.name}
            elif attribute == "storage":
                witnesses["storage_type"] = type(right).__module__ + "." + type(right).__qualname__
        except AttributeError as exc:
            import traceback
            check = {"status": "ATTRIBUTE_ERROR", "equal": None,
                     "error": {"type_fqn": type(exc).__module__ + "." + type(exc).__qualname__,
                               "message": str(exc), "observed_attribute": attribute,
                               "traceback": traceback.format_exc()}}
        checks[attribute] = check
        emit("PROPERTY_CHECK:" + attribute, check)
    result = {"serialization_calls": 1, "restoration_calls": 1, "pickle_protocol": 4,
              "file_type": type(restored).__module__ + "." + type(restored).__qualname__,
              "checks": checks, "witnesses": witnesses,
              "native_access_error_count": sum(x["status"] == "ATTRIBUTE_ERROR" for x in checks.values()),
              "terminal": "RESTORATION_AND_CHECKS_COMPLETE"}
    emit("TERMINAL_SNAPSHOT", result)
    return result

