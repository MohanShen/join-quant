# Clone from JoinQuant
# postId: 7df495326a36170da73a4417e2933122
# backtestId: 274531f88195933826ce970b5f564565
# title: 成功！一劳永逸绕开Q-M-T限制，直接联网！

def initialize(c):
    g.n = 0
    g.s = '513130.XSHG'
    run_daily(f, 'every_bar')

def f(c):
    g.n += 1
    if g.n % 5:
        return
    h = attribute_history(g.s, 5, '1m', ['close'])
    if len(h) < 5:
        return
    # 手动计算目标金额：总资产 * 目标比例
    target_value = c.portfolio.total_value * 0.95
    if h['close'][-1] > h['close'].mean():
        order_target_value(g.s, target_value)  # 调至目标金额
    else:
        order_target_value(g.s, 0)             # 清仓

#下面填入QMT代码

'''
importsys
importtraceback

CONDA_DLLS=r'D:\ProgramFiles\Anaconda3\envs\py36\DLLs'


definit(ContextInfo):
    print('========== QMT SOCKET TEST ==========')

    try:
        # 1. Load socket from Conda
        ifCONDA_DLLSnotinsys.path:
            sys.path.append(CONDA_DLLS)

        importsocket
        importthreading

        print('[SOCKET] IMPORT SUCCESS')

        # Server startup event
        ready=threading.Event()
        state= {'port': None, 'received': None, 'error': None}

        # 2. TCP server thread
        deftcp_server():
            server=None
            conn=None

            try:
                server=socket.socket(
                    socket.AF_INET,
                    socket.SOCK_STREAM
                )

                server.setsockopt(
                    socket.SOL_SOCKET,
                    socket.SO_REUSEADDR,
                    1
                )

                server.settimeout(3)

                # Port 0: automatically choose a free port
                server.bind(('127.0.0.1', 0))
                server.listen(1)

                state['port'] =server.getsockname()[1]

                print('[SERVER] LISTEN PORT:', state['port'])
                ready.set()

                conn, addr=server.accept()
                conn.settimeout(3)

                print('[SERVER] CLIENT CONNECTED:', addr)

                data=conn.recv(1024)
                state['received'] =data

                print('[SERVER] RECEIVED:', repr(data))

                conn.sendall(b'PONG_FROM_QMT_SERVER')
                print('[SERVER] RESPONSE SENT')

            exceptExceptionase:
                state['error'] =repr(e)
                print('[SERVER ERROR]', repr(e))
                traceback.print_exc()

            finally:
                ready.set()

                ifconnisnotNone:
                    conn.close()

                ifserverisnotNone:
                    server.close()

                print('[SERVER] STOPPED')

        # 3. Start server thread
        thread=threading.Thread(target=tcp_server)
        thread.daemon=True
        thread.start()

        # 4. Wait until server is listening
        ifnotready.wait(3):
            print('[FAILED] Server startup timeout')
            return

        ifstate['port'] isNone:
            print('[FAILED] Server startup:', state['error'])
            return

        # 5. TCP client test
        client=None

        try:
            client=socket.create_connection(
                ('127.0.0.1', state['port']),
                timeout=3
            )

            client.settimeout(3)

            print('[CLIENT] CONNECT SUCCESS')

            client.sendall(b'PING_FROM_QMT_CLIENT')
            print('[CLIENT] DATA SENT')

            response=client.recv(1024)

            print('[CLIENT] RECEIVED:', repr(response))

            ifresponse==b'PONG_FROM_QMT_SERVER':
                print('[CLIENT] RESPONSE VERIFIED')
            else:
                print('[CLIENT] RESPONSE INVALID')

        exceptExceptionase:
            print('[CLIENT ERROR]', repr(e))
            traceback.print_exc()

        finally:
            ifclientisnotNone:
                client.close()

        # 6. Wait for server to finish
        thread.join(5)

        ifthread.is_alive():
            print('[TEST] SERVER THREAD STILL RUNNING')

        elif (state['received'] ==b'PING_FROM_QMT_CLIENT'
              andstate['error'] isNone
              andresponse==b'PONG_FROM_QMT_SERVER'):
            print('[TEST] TCP BIDIRECTIONAL SUCCESS')

        else:
            print('[TEST] FAILED')

    exceptExceptionase:
        print('[ERROR]', repr(e))
        traceback.print_exc()

    print('========== TEST FINISHED ==========')


defhandlebar(ContextInfo):
    pass
    
    
'''