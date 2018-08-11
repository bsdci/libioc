deploy:
	rm -r *.html *.js _*
	cp -r docs/_build/html/* .
	git add .
	git commit -m "auto-generate docs"
