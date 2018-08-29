.PHONY: check checkall demo democlean develop install _check _checkall

check:
	pipenv run make _check

checkall:
	pipenv run make _checkall

_check:
	flake8 jeff65 tests
	python setup.py nosetests -a "!vice"

_checkall:
	flake8 jeff65 tests
	python setup.py nosetests

install:
	pipenv sync

develop:
	pipenv sync --dev

demo: examples/heart.prg
	x64 $<

democlean:
	-rm examples/*.blum examples/*.prg

examples/heart.prg: examples/heart.gold
	pipenv run jeff65 compile $<
