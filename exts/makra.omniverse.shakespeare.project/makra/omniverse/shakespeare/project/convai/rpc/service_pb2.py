"""Generated protocol buffer code."""
from google.protobuf.internal import builder as _builder
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database

_sym_db = _symbol_database.Default()

DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\rservice.proto\x12\x07service\"(\n\x0b\x41udioConfig\x12\x19\n\x11sample_rate_hertz\x18\x01 \x01(\x05\"\x87\x02\n\x0c\x41\x63tionConfig\x12\x0f\n\x07\x61\x63tions\x18\x01 \x03(\t\x12\x33\n\ncharacters\x18\x02 \x03(\x0b\x32\x1f.service.ActionConfig.Character\x12-\n\x07objects\x18\x03 \x03(\x0b\x32\x1c.service.ActionConfig.Object\x12\x16\n\x0e\x63lassification\x18\x04 \x01(\t\x12\x15\n\rcontext_level\x18\x05 \x01(\x05\x1a&\n\tCharacter\x12\x0c\n\x04name\x18\x01 \x01(\t\x12\x0b\n\x03\x62io\x18\x02 \x01(\t\x1a+\n\x06Object\x12\x0c\n\x04name\x18\x01 \x01(\t\x12\x13\n\x0b\x64\x65scription\x18\x02 \x01(\t\"a\n\nSTTRequest\x12,\n\x0c\x61udio_config\x18\x01 \x01(\x0b\x32\x14.service.AudioConfigH\x00\x12\x15\n\x0b\x61udio_chunk\x18\x02 \x01(\x0cH\x00\x42\x0e\n\x0crequest_type\"\x1b\n\x0bSTTResponse\x12\x0c\n\x04text\x18\x01 \x01(\t\"\xc4\x03\n\x12GetResponseRequest\x12L\n\x13get_response_config\x18\x01 \x01(\x0b\x32-.service.GetResponseRequest.GetResponseConfigH\x00\x12H\n\x11get_response_data\x18\x02 \x01(\x0b\x32+.service.GetResponseRequest.GetResponseDataH\x00\x1a\xb9\x01\n\x11GetResponseConfig\x12\x14\n\x0c\x63haracter_id\x18\x02 \x01(\t\x12\x0f\n\x07\x61pi_key\x18\x03 \x01(\t\x12\x12\n\nsession_id\x18\x04 \x01(\t\x12*\n\x0c\x61udio_config\x18\x05 \x01(\x0b\x32\x14.service.AudioConfig\x12,\n\raction_config\x18\x06 \x01(\x0b\x32\x15.service.ActionConfig\x12\x0f\n\x07speaker\x18\x07 \x01(\t\x1aJ\n\x0fGetResponseData\x12\x14\n\naudio_data\x18\x01 \x01(\x0cH\x00\x12\x13\n\ttext_data\x18\x02 \x01(\tH\x00\x42\x0c\n\ninput_typeB\x0e\n\x0crequest_type\"\x84\x01\n\x18GetResponseRequestSingle\x12\x34\n\x0fresponse_config\x18\x01 \x01(\x0b\x32\x1b.service.GetResponseRequest\x12\x32\n\rresponse_data\x18\x02 \x01(\x0b\x32\x1b.service.GetResponseRequest\"\x8f\x04\n\x13GetResponseResponse\x12\x12\n\nsession_id\x18\x01 \x01(\t\x12\x46\n\x0f\x61\x63tion_response\x18\x02 \x01(\x0b\x32+.service.GetResponseResponse.ActionResponseH\x00\x12\x44\n\x0e\x61udio_response\x18\x03 \x01(\x0b\x32*.service.GetResponseResponse.AudioResponseH\x00\x12\x13\n\tdebug_log\x18\x04 \x01(\tH\x00\x12\x41\n\nuser_query\x18\x05 \x01(\x0b\x32+.service.GetResponseResponse.UserTranscriptH\x00\x1a{\n\rAudioResponse\x12\x12\n\naudio_data\x18\x01 \x01(\x0c\x12*\n\x0c\x61udio_config\x18\x02 \x01(\x0b\x32\x14.service.AudioConfig\x12\x11\n\ttext_data\x18\x03 \x01(\t\x12\x17\n\x0f\x65nd_of_response\x18\x04 \x01(\x08\x1a \n\x0e\x41\x63tionResponse\x12\x0e\n\x06\x61\x63tion\x18\x01 \x01(\t\x1aN\n\x0eUserTranscript\x12\x11\n\ttext_data\x18\x01 \x01(\t\x12\x10\n\x08is_final\x18\x02 \x01(\x08\x12\x17\n\x0f\x65nd_of_response\x18\x03 \x01(\x08\x42\x0f\n\rresponse_type\"\x1c\n\x0cHelloRequest\x12\x0c\n\x04name\x18\x01 \x01(\t\" \n\rHelloResponse\x12\x0f\n\x07message\x18\x01 \x01(\t2\xf8\x02\n\rConvaiService\x12\x38\n\x05Hello\x12\x15.service.HelloRequest\x1a\x16.service.HelloResponse\"\x00\x12\x42\n\x0bHelloStream\x12\x15.service.HelloRequest\x1a\x16.service.HelloResponse\"\x00(\x01\x30\x01\x12?\n\x0cSpeechToText\x12\x13.service.STTRequest\x1a\x14.service.STTResponse\"\x00(\x01\x30\x01\x12N\n\x0bGetResponse\x12\x1b.service.GetResponseRequest\x1a\x1c.service.GetResponseResponse\"\x00(\x01\x30\x01\x12X\n\x11GetResponseSingle\x12!.service.GetResponseRequestSingle\x1a\x1c.service.GetResponseResponse\"\x00\x30\x01\x62\x06proto3')

_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, globals())
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'service_pb2', globals())
if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  _AUDIOCONFIG._serialized_start=26
  _AUDIOCONFIG._serialized_end=66
  _ACTIONCONFIG._serialized_start=69
  _ACTIONCONFIG._serialized_end=332
  _ACTIONCONFIG_CHARACTER._serialized_start=249
  _ACTIONCONFIG_CHARACTER._serialized_end=287
  _ACTIONCONFIG_OBJECT._serialized_start=289
  _ACTIONCONFIG_OBJECT._serialized_end=332
  _STTREQUEST._serialized_start=334
  _STTREQUEST._serialized_end=431
  _STTRESPONSE._serialized_start=433
  _STTRESPONSE._serialized_end=460
  _GETRESPONSEREQUEST._serialized_start=463
  _GETRESPONSEREQUEST._serialized_end=915
  _GETRESPONSEREQUEST_GETRESPONSECONFIG._serialized_start=638
  _GETRESPONSEREQUEST_GETRESPONSECONFIG._serialized_end=823
  _GETRESPONSEREQUEST_GETRESPONSEDATA._serialized_start=825
  _GETRESPONSEREQUEST_GETRESPONSEDATA._serialized_end=899
  _GETRESPONSEREQUESTSINGLE._serialized_start=918
  _GETRESPONSEREQUESTSINGLE._serialized_end=1050
  _GETRESPONSERESPONSE._serialized_start=1053
  _GETRESPONSERESPONSE._serialized_end=1580
  _GETRESPONSERESPONSE_AUDIORESPONSE._serialized_start=1326
  _GETRESPONSERESPONSE_AUDIORESPONSE._serialized_end=1449
  _GETRESPONSERESPONSE_ACTIONRESPONSE._serialized_start=1451
  _GETRESPONSERESPONSE_ACTIONRESPONSE._serialized_end=1483
  _GETRESPONSERESPONSE_USERTRANSCRIPT._serialized_start=1485
  _GETRESPONSERESPONSE_USERTRANSCRIPT._serialized_end=1563
  _HELLOREQUEST._serialized_start=1582
  _HELLOREQUEST._serialized_end=1610
  _HELLORESPONSE._serialized_start=1612
  _HELLORESPONSE._serialized_end=1644
  _CONVAISERVICE._serialized_start=1647
  _CONVAISERVICE._serialized_end=2023