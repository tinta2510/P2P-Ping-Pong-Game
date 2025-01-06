import pygame
import socket
import threading
import json

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

def recv_json(sock):
    buffer = ""
    while True:
        data = sock.recv(1024).decode()
        buffer += data
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            yield json.loads(line)

def handle_networking(role, paddle, opponent_paddle, ball):
    if role == 'host':
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind(('0.0.0.0', 12345))
        server_socket.listen(1)
        conn, _ = server_socket.accept()
        conn_file = conn.makefile('rw')
        while True:
            data = {
                'paddle_y': paddle.y,
                'ball_x': ball.x,
                'ball_y': ball.y,
                'ball_speed_x': ball.speed_x,
                'ball_speed_y': ball.speed_y
            }
            conn_file.write(json.dumps(data) + "\n")
            conn_file.flush()
            received_data = json.loads(conn_file.readline())
            opponent_paddle.y = received_data['paddle_y']
    elif role == 'client':
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect(('127.0.0.1', 12345))
        client_file = client_socket.makefile('rw')
        while True:
            client_file.write(json.dumps({'paddle_y': paddle.y}) + "\n")
            client_file.flush()
            data = json.loads(client_file.readline())
            opponent_paddle.y = data['paddle_y']
            ball.x = data['ball_x']
            ball.y = data['ball_y']
            ball.speed_x = data['ball_speed_x']
            ball.speed_y = data['ball_speed_y']

def main(role):
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Ping Pong Online")
    clock = pygame.time.Clock()

    paddle = Paddle(50 if role == 'host' else SCREEN_WIDTH - 60, SCREEN_HEIGHT // 2 - PADDLE_HEIGHT // 2)
    opponent_paddle = Paddle(SCREEN_WIDTH - 60 if role == 'host' else 50, SCREEN_HEIGHT // 2 - PADDLE_HEIGHT // 2)
    ball = Ball()

    networking_thread = threading.Thread(target=handle_networking, args=(role, paddle, opponent_paddle, ball), daemon=True)
    networking_thread.start()

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        keys = pygame.key.get_pressed()
        if keys[pygame.K_UP]:
            paddle.move_up()
        if keys[pygame.K_DOWN]:
            paddle.move_down()

        if role == 'host':
            ball.move()

            # Ball collision with paddles
            if (ball.x <= paddle.x + PADDLE_WIDTH and paddle.y < ball.y < paddle.y + PADDLE_HEIGHT) or \
               (ball.x + BALL_SIZE >= opponent_paddle.x and opponent_paddle.y < ball.y < opponent_paddle.y + PADDLE_HEIGHT):
                ball.speed_x *= -1

            # Ball goes out of bounds
            if ball.x <= 0 or ball.x >= SCREEN_WIDTH:
                ball.reset()

        # Drawing
        screen.fill(BLACK)
        paddle.draw(screen)
        opponent_paddle.draw(screen)
        ball.draw(screen)
        pygame.display.flip()

        clock.tick(FPS)

    pygame.quit()

if __name__ == "__main__":
    role = input("Enter 'host' to host the game or 'client' to join: ").strip().lower()
    main(role)
