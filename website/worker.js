// MIT. Firmware arrives by transferable ArrayBuffer and never leaves this worker.
'use strict';
importScripts('recipe-pin.js', 'recipe.js', 'patcher.js');
self.onmessage = async event => {
  try {
    const {output, report} = await PX.build(new Uint8Array(event.data), message => self.postMessage({progress: message}));
    self.postMessage({output: output.buffer, report}, [output.buffer]);
  } catch (error) { self.postMessage({error: error.message}); }
};
