def wait_joined(viewer):
    # websocket_connect returns once the socket is accepted, before connect() adds it
    # to the room: a reply proves the chat loop runs, so the viewer gets broadcasts
    viewer.send_json({"content": "hello"})
    assert viewer.receive_json()["code"] == "READ_ONLY"
