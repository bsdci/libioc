deploy:
	rm -r *.html *.js _*
	cp -r build/sphinx/html/* .
	git add .
	git commit -m "auto-generate docs"
