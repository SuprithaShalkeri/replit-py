import zmq

from . import context as context
from . import logger as log
from .serialization import pack, unpack
from .polling import _register


# Decorator that marks a function as being an rpc target
def rpc(callback):
    name = callback.__name__

    # Listen on a ZMQ port
    socket = context.socket(zmq.ROUTER)
    socket.setsockopt(zmq.IDENTITY, name.encode('ascii'))
    log.debug("Connecting to /tmp/router %s", name)
    socket.connect("ipc:///tmp/router")

    # Call the callback and write the response to the stream
    def callback_wrapper(message):
        # Decode the message to get the RPC arguments
        [session, _, routing, payload] = message

        routing = unpack(routing)
        payload = unpack(payload)
        args = payload['args']
        kwargs = payload['kwargs']

        log.info("Recieved RPC call to %s with args (%s, %s) from %s",
                 name,
                 args,
                 kwargs,
                 routing['source'])

        # Call the RPC provider
        try:
            response = callback(*args, **kwargs)
        except Exception as e:
            log.warning("Exception occured while processing RPC callback %s", e)
            response = e

        # Update the routing information to use for reply
        routing['dest'] = routing['source']
        routing['destService'] = routing['sourceService']
        routing = pack(routing)

        # Send the reply
        log.info("Sending RPC response from %s with %s", name, response)
        socket.send_multipart(message[:2] + [routing, pack(response)])

    # Register the socket so it can be polled
    log.info("Loaded RPC callback for %s", name)
    _register(socket, callback_wrapper)

    return callback
