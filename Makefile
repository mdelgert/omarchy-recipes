.PHONY: test validate demo clean-demo

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

validate:
	./bin/omarchy-recipes validate

demo:
	./bin/omarchy-recipes run example-config-value --value balanced
	./bin/omarchy-recipes check example-config-value

clean-demo:
	./bin/omarchy-recipes undo example-config-value
