deploy:
	if [ -d api/ ]; then rm -r api/; fi
	mkdir api/
	cp -r docs/_build/html/* api/
	git add api
	git commit -m "auto-generate docs"
