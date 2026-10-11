source env/bin/activate
rm -rf build
export FLET_PYTHON_BUILD_MANIFEST=./manifest.json
flet build apk