"""Client and server classes corresponding to protobuf-defined services."""
import grpc

from . import service_pb2 as service__pb2

class ConvaiServiceStub(object):
    """Missing associated documentation comment in .proto file."""

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.Hello = channel.unary_unary(
                '/service.ConvaiService/Hello',
                request_serializer=service__pb2.HelloRequest.SerializeToString,
                response_deserializer=service__pb2.HelloResponse.FromString,
                )
        self.HelloStream = channel.stream_stream(
                '/service.ConvaiService/HelloStream',
                request_serializer=service__pb2.HelloRequest.SerializeToString,
                response_deserializer=service__pb2.HelloResponse.FromString,
                )
        self.SpeechToText = channel.stream_stream(
                '/service.ConvaiService/SpeechToText',
                request_serializer=service__pb2.STTRequest.SerializeToString,
                response_deserializer=service__pb2.STTResponse.FromString,
                )
        self.GetResponse = channel.stream_stream(
                '/service.ConvaiService/GetResponse',
                request_serializer=service__pb2.GetResponseRequest.SerializeToString,
                response_deserializer=service__pb2.GetResponseResponse.FromString,
                )
        self.GetResponseSingle = channel.unary_stream(
                '/service.ConvaiService/GetResponseSingle',
                request_serializer=service__pb2.GetResponseRequestSingle.SerializeToString,
                response_deserializer=service__pb2.GetResponseResponse.FromString,
                )

class ConvaiServiceServicer(object):
    """Missing associated documentation comment in .proto file."""

    def Hello(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def HelloStream(self, request_iterator, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def SpeechToText(self, request_iterator, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def GetResponse(self, request_iterator, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def GetResponseSingle(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

def add_ConvaiServiceServicer_to_server(servicer, server):
    rpc_method_handlers = {
            'Hello': grpc.unary_unary_rpc_method_handler(
                    servicer.Hello,
                    request_deserializer=service__pb2.HelloRequest.FromString,
                    response_serializer=service__pb2.HelloResponse.SerializeToString,
            ),
            'HelloStream': grpc.stream_stream_rpc_method_handler(
                    servicer.HelloStream,
                    request_deserializer=service__pb2.HelloRequest.FromString,
                    response_serializer=service__pb2.HelloResponse.SerializeToString,
            ),
            'SpeechToText': grpc.stream_stream_rpc_method_handler(
                    servicer.SpeechToText,
                    request_deserializer=service__pb2.STTRequest.FromString,
                    response_serializer=service__pb2.STTResponse.SerializeToString,
            ),
            'GetResponse': grpc.stream_stream_rpc_method_handler(
                    servicer.GetResponse,
                    request_deserializer=service__pb2.GetResponseRequest.FromString,
                    response_serializer=service__pb2.GetResponseResponse.SerializeToString,
            ),
            'GetResponseSingle': grpc.unary_stream_rpc_method_handler(
                    servicer.GetResponseSingle,
                    request_deserializer=service__pb2.GetResponseRequestSingle.FromString,
                    response_serializer=service__pb2.GetResponseResponse.SerializeToString,
            ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
            'service.ConvaiService', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))


class ConvaiService(object):
    """Missing associated documentation comment in .proto file."""

    @staticmethod
    def Hello(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/service.ConvaiService/Hello',
            service__pb2.HelloRequest.SerializeToString,
            service__pb2.HelloResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def HelloStream(request_iterator,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.stream_stream(request_iterator, target, '/service.ConvaiService/HelloStream',
            service__pb2.HelloRequest.SerializeToString,
            service__pb2.HelloResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def SpeechToText(request_iterator,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.stream_stream(request_iterator, target, '/service.ConvaiService/SpeechToText',
            service__pb2.STTRequest.SerializeToString,
            service__pb2.STTResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def GetResponse(request_iterator,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.stream_stream(request_iterator, target, '/service.ConvaiService/GetResponse',
            service__pb2.GetResponseRequest.SerializeToString,
            service__pb2.GetResponseResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def GetResponseSingle(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_stream(request, target, '/service.ConvaiService/GetResponseSingle',
            service__pb2.GetResponseRequestSingle.SerializeToString,
            service__pb2.GetResponseResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)