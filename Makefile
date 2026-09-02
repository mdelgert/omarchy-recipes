.PHONY: test test-qml lint-qml check plugin demo clean-demo validate

# Qt tools are not on PATH on a stock Arch/Omarchy install.
QT_BIN ?= /usr/lib/qt6/bin
# The Omarchy shell exports `qs.*` from its own tree; qmllint needs a directory
# where that tree is reachable as `qs`.
OMARCHY_PATH ?= /usr/share/omarchy
# Built outside the repository on purpose: Omarchy refuses a plugin folder that
# contains a symlink, and this tree must stay directly installable.
QML_IMPORTS := $(shell mktemp -d -u /tmp/omarchy-recipes-qml.XXXXXX 2>/dev/null || echo /tmp/omarchy-recipes-qml)

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

test-qml:
	QT_QPA_PLATFORM=offscreen $(QT_BIN)/qmltestrunner -input tests/qml

$(QML_IMPORTS)/qs:
	mkdir -p $(QML_IMPORTS)
	ln -sfn $(OMARCHY_PATH)/shell $(QML_IMPORTS)/qs

lint-qml: $(QML_IMPORTS)/qs
	$(QT_BIN)/qmllint -I $(QML_IMPORTS) omarchy-plugin/*.qml

check: test test-qml validate

validate:
	./bin/omarchy-recipes validate

plugin:
	./omarchy-plugin/install.sh

demo:
	./bin/omarchy-recipes run example-config-value --value balanced
	./bin/omarchy-recipes check example-config-value

clean-demo:
	./bin/omarchy-recipes undo example-config-value
