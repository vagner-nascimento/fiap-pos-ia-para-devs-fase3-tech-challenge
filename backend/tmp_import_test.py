import sys, traceback, importlib
sys.path.insert(0, 'backend/src')
importlib.invalidate_caches()
try:
    import routers.preprocess
except Exception:
    traceback.print_exc()
print('IMPORT_DONE')
