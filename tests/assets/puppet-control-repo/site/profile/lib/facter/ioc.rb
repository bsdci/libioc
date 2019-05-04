#
# Add custom facts as passed on by (lib)ioc thru the execution environment
#
# Our facts are placed into user.facts.x which generates an environment variable
# named IOC_USER_FACTS_X, which then is reduced to :x and its value.
#
prefix = 'IOC_USER_FACTS_'
facts = ENV.select { |x| x.start_with? prefix }
facts.each do |k, v|
  fact = k.slice(prefix.length, k.size - prefix.size).downcase.to_sym
  Facter.add(fact) do
    confine virtual: 'jail'
    setcode { v }
  end
end
