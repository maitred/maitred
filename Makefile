default: test
.PHONY: default test

test:
	venv/bin/python -m unittest discover test -v
