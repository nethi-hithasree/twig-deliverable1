.PHONY: install run clean
install:
	python -m pip install -r requirements.txt
run:
	python -m pipeline.main
clean:
	python -c "import shutil; shutil.rmtree('data/raw', ignore_errors=True);"
