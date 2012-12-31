var tm = require('./test_module');
var a = 'Hello';
var b = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
var x = [22, 14, 17, 11, 3];
var message = a +' ';

x.forEach(function(i){
  message += b[i];
})

console.log(message);   // should output: hello WORLD
console.log( Math.PI ); // yum!

tm.bar(); // yes, this is eval'd as a node script. outputs: foobar
