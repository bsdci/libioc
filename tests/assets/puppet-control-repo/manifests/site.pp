# Since all we do in this control repo is install, this should suffice
contain nginx


$hello_world = @("HELLO")
<html>
  <head>
    <title>Hello, World</title>
  </head>
  <body>
    <h1>Hello, World</h1>
    <p>Hello, World</p>
  </body>
</html>
HELLO

nginx::resource::server { 'webserer':
  www_root => '/usr/local/www/nginx-dist',
}
-> file { '/usr/local/www/nginx-dist/index.html':
  ensure  => file,
  content => $hello_world,
}
