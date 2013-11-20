var tm = require('./test_module');
var a = 'Hello';
var b = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
var x = [22, 14, 17, 11, 3];
var message = a +' ';

x.forEach(function(i){
  message += b[i];
})

console.log(message);     // hello WORLD
console.log( Math.PI );   // 3.141592653589793
console.log( tm.bar() );  // foobar

// The following will lock up SublimeText for 10 seconds in Windows OS
setTimeout(function(){
    console.log('Goodbye');
}, 10000);