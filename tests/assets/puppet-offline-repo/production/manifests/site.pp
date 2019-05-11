# fully offline test

$hello_puppet = @("HELLO")
Puppet test is successful
HELLO

file { '/puppet.test':
  ensure  => file,
  content => $hello_puppet,
}
