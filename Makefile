deploy:
	rm -r *.html *.js _modules/ _sources/ _static/
	cp -r docs/_build/html/* .
	git add .
	git commit -m "auto-generate docs"
