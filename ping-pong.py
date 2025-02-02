import pygame
import socket
import threading
import json
import time
import random

# Game Constants
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 400
BALL_SIZE = 15
PADDLE_WIDTH = 10
PADDLE_HEIGHT = 100
FPS = 60

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

class Paddle:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.speed = 5

    def move_up(self):
        if self.y > 0:
            self.y -= self.speed

    def move_down(self):
        if self.y < SCREEN_HEIGHT - PADDLE_HEIGHT:
            self.y += self.speed

    def draw(self, screen):
        pygame.draw.rect(screen, WHITE, (self.x, self.y, PADDLE_WIDTH, PADDLE_HEIGHT))

class Ball:
    def __init__(self):
        self.x = SCREEN_WIDTH // 2
        self.y = SCREEN_HEIGHT // 2
        self.speed_x = 4
        self.speed_y = 4

    def move(self):
        self.x += self.speed_x
        self.y += self.speed_y

        if self.y <= 0 or self.y >= SCREEN_HEIGHT - BALL_SIZE:
            self.speed_y *= -1

    def reset(self):
        self.x = SCREEN_WIDTH // 2
        self.y = SCREEN_HEIGHT // 2
        self.speed_x *= -1

    def draw(self, screen):
        pygame.draw.ellipse(screen, WHITE, (self.x, self.y, BALL_SIZE, BALL_SIZE))

class Player:
    def __init__(self, role, peer_name, listen_port=random.randint(10000, 60000), on_local_machine=True):
        self.role = role
        self.peer_name = peer_name
        self.listen_port = listen_port
        self.on_local_machine = on_local_machine

    def game_main(self):
        pygame.init()
        screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Ping Pong Online - Player: " + self.peer_name + " - Role: " + self.role)
        clock = pygame.time.Clock()

        paddle = Paddle(50 if self.role == 'host' else SCREEN_WIDTH - 60, SCREEN_HEIGHT // 2 - PADDLE_HEIGHT // 2)
        opponent_paddle = Paddle(SCREEN_WIDTH - 60 if self.role == 'host' else 50, SCREEN_HEIGHT // 2 - PADDLE_HEIGHT // 2)
        ball = Ball()

        scores = [0, 0]  # [Host score, Client score]
        game_state = {'running': True}  # Control game state
        space_pressed = False  # Prevent repeated toggles on a single press

        if self.role == 'host':
            networking_thread = threading.Thread(target=self.handle_networking_host, args=(paddle, opponent_paddle, ball, scores, game_state), daemon=True)
        else:  # role is client
            networking_thread = threading.Thread(target=self.handle_networking_client, args=(paddle, opponent_paddle, ball, scores, game_state), daemon=True)

        networking_thread.start()

        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

            keys = pygame.key.get_pressed()

            # Host can toggle game running state
            if self.role == 'host':
                if keys[pygame.K_SPACE] and not space_pressed:
                    game_state['running'] = not game_state['running']
                    space_pressed = True
                if not keys[pygame.K_SPACE]:
                    space_pressed = False

            if game_state['running']:
                if keys[pygame.K_UP]:
                    paddle.move_up()
                if keys[pygame.K_DOWN]:
                    paddle.move_down()

                if self.role == 'host':
                    ball.move()

                    # Ball collision with paddles
                    # if (ball.x <= paddle.x + PADDLE_WIDTH and paddle.y < ball.y < paddle.y + PADDLE_HEIGHT) or \
                    #         (ball.x + BALL_SIZE >= opponent_paddle.x and opponent_paddle.y < ball.y < opponent_paddle.y + PADDLE_HEIGHT):
                    #     ball.speed_x *= -1
                    if (ball.x == paddle.x + PADDLE_WIDTH and paddle.y < ball.y < paddle.y + PADDLE_HEIGHT) or \
                            (opponent_paddle.x+5 >= ball.x + BALL_SIZE >= opponent_paddle.x and opponent_paddle.y < ball.y < opponent_paddle.y + PADDLE_HEIGHT):
                        ball.speed_x *= -1

                    # Ball goes out of bounds
                    if ball.x <= 0:
                        scores[1] += 1  # Client scores
                        ball.reset()
                    elif ball.x >= SCREEN_WIDTH:
                        scores[0] += 1  # Host scores
                        ball.reset()

            # Drawing
            screen.fill(BLACK)
            paddle.draw(screen)
            opponent_paddle.draw(screen)
            ball.draw(screen)
            
            pygame.draw.line(screen, WHITE, (screen.get_width() // 2, 0), (screen.get_width() // 2, screen.get_height()), 5)

            # Draw scores
            font = pygame.font.Font(None, 74)
            score_text = font.render(f"{scores[0]} - {scores[1]}", True, WHITE)
            screen.blit(score_text, (SCREEN_WIDTH // 2 - score_text.get_width() // 2, 10))

            # Draw pause message if game is stopped
            if not game_state['running']:
                pause_text = font.render("Paused", True, WHITE)
                screen.blit(pause_text, (SCREEN_WIDTH // 2 - pause_text.get_width() // 2, SCREEN_HEIGHT // 2 - pause_text.get_height() // 2))

            pygame.display.flip()
            clock.tick(FPS)

        pygame.quit()

class Host(Player):
    def __init__(self, peer_name, listen_port=random.randint(10000, 60000), on_local_machine=True):
        super().__init__('host', peer_name, listen_port, on_local_machine)
        self.conn = None
        self.is_broadcasting = True

    def handle_networking_host(self, paddle, opponent_paddle, ball, scores, game_state):
        conn_file = self.conn.makefile('rw')
        while True:
            data = {
                'paddle_y': paddle.y,
                'ball_x': ball.x,
                'ball_y': ball.y,
                'ball_speed_x': ball.speed_x,
                'ball_speed_y': ball.speed_y,
                'scores': scores,
                'game_running': game_state['running']
            }
            conn_file.write(json.dumps(data) + "\n")
            conn_file.flush()
            received_data = json.loads(conn_file.readline())
            opponent_paddle.y = received_data['paddle_y']

    def broadcast_existence(self, broadcast_port=12345):
        broadcast_addr = "255.255.255.255"
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            while self.is_broadcasting:
                msg = f'{self.peer_name}|{self.listen_port}'
                s.sendto(msg.encode(), (broadcast_addr, broadcast_port))
                time.sleep(1)  # broadcast every 2 seconds

    def listen(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind(('0.0.0.0', self.listen_port))
        print(f"Server is running on port {self.listen_port}")
        server_socket.listen(1)

        # reuse the address (ip + port) in case that address is already in use
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            while True:
                self.conn, client_address = server_socket.accept()
                self.other_peer_name = self.conn.recv(1024).decode()

                # ask the player if they want to play with the other player, if no, close the connection
                while True:
                    key = input(f"Do you want to play with player '{self.other_peer_name}'? (y/n)")
                    if key == "y":
                        self.is_broadcasting = False
                        self.conn.send("start".encode())
                        print(f"Connected with {client_address}, player's name: {self.other_peer_name}")
                        self.game_main()
                        break
                    elif key == "n":
                        self.conn.send(f"{self.peer_name} has refused to play".encode())
                        self.conn.close()
                        print(f"Refused playing with {self.other_peer_name}")
                        break
                    else:
                        print("Invalid input. Please enter 'y' or 'n'")
        except Exception as e:
            print(f"Error: {e}")
            server_socket.close()
            print("Server is closed")

    def run_host(self):
        listen_thread = threading.Thread(target=self.listen, daemon=True)
        # broadcast existence, despite is playing or not
        broadcast_thread = threading.Thread(target=self.broadcast_existence, daemon=True)

        listen_thread.start()
        broadcast_thread.start()

        listen_thread.join()
        broadcast_thread.join()

class Client(Player):
    def __init__(self, peer_name, listen_port=random.randint(10000, 60000), on_local_machine=True):
        super().__init__('client', peer_name, listen_port, on_local_machine)
        self.client_socket = None

    def handle_networking_client(self, paddle, opponent_paddle, ball, scores, game_state):
        client_file = self.client_socket.makefile('rw')
        while True:
            client_file.write(json.dumps({'paddle_y': paddle.y}) + "\n")
            client_file.flush()
            data = json.loads(client_file.readline())
            opponent_paddle.y = data['paddle_y']
            ball.x = data['ball_x']
            ball.y = data['ball_y']
            ball.speed_x = data['ball_speed_x']
            ball.speed_y = data['ball_speed_y']
            scores[0] = data['scores'][0]
            scores[1] = data['scores'][1]
            game_state['running'] = data['game_running']

    def discover_exposed_host(self, player_list: list, listen_port=12345):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("", listen_port))
            while True:
                message, address = s.recvfrom(1024)

                # take the player's name from the message
                parts = message.decode().split("|")
                player_name = parts[0]
                player_port = int(parts[-1])
                player = (player_name, address[0], player_port)
                # put player's name and ip into the queue
                if player not in player_list:
                    player_list.append(player)

    def discover_choose_players(self) -> tuple[str, str, int]:
        player_list = []
        # discover other hosts playing the game -> ask the user to choose one to connect
        discover_thread = threading.Thread(target=self.discover_exposed_host, args=(player_list,), daemon=True)
        discover_thread.start()
        while True:
            if not player_list:
                print("No player is found. Continue searching for players...")
                time.sleep(2)
                continue
            else:
                print(f"List of players found:")
                for idx, player in enumerate(player_list):
                    print(f"{idx}: {player}")

                while True:
                    player_idx = int(input(f"Choose a player to connect (0-{len(player_list) - 1}): "))
                    if player_idx in range(len(player_list)):
                        print(f"Player chosen: {player_idx}")
                        print(f"Player chosen: {player_list[player_idx]}")
                        return player_list[player_idx]
                    else:
                        print("Continue searching for players...")
                        break
                time.sleep(5)
                
    def connect(self):
        # for sending data
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # put connecting attempt in a loop because the player chosen can be offline right after -> need to choose player again
        while not self.attempt_connecting(self.client_socket):
            print("Continue searching for players...")
            continue

        try:
            print("Connecting to the host...")
            start_msg = self.client_socket.recv(1024).decode()
            if start_msg == "start":
                print("Connected to server. Game is starting...")
                self.game_main()
        except Exception as e:
            print(f"Error: {e}")
            self.client_socket.close()
            print("Client is closed")

    def attempt_connecting(self, client_socket):
        n_attempts = 3
        player = self.discover_choose_players()

        if self.on_local_machine:
            self.connect_address = "127.0.0.1"
        else:
            self.connect_address = player[1]  # idx 0 is the player's name, idx 1 is the player's ip
        self.connect_port = player[2]  # idx 2 is the player's port

        # try to connect to the server after every 10 seconds
        for _ in range(n_attempts):
            try:
                client_socket.connect((self.connect_address, self.connect_port))
                print(f"Connected To server at {self.connect_address}:{self.connect_port}")
                client_socket.send(self.peer_name.encode())
                return True
            except ConnectionRefusedError:
                print("Connection refused. Retrying in 10 seconds...")
                time.sleep(10)
                continue
        print(f"Cannot connect to {self.connect_address} after {n_attempts} attempts")
        return False

if __name__ == "__main__":
    peer_name = input("Enter your name: ").strip()
    while True:
        role = input("Enter 'host' to host the game or 'client' to join: ").strip().lower()
        if role == 'host':
            player = Host(peer_name)
            player.run_host()
            break
        elif role == 'client':
            player = Client(peer_name)
            player.connect()
            break
        else:
            print("Invalid role. Enter 'host' or 'client'.")
    
        