import pygame
import socket
import threading
import json
import time

# Game Constants
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 400
BALL_SIZE = 15
PADDLE_WIDTH = 10
PADDLE_HEIGHT = 100
FPS = 60
COLLISION_COOLDOWN = 0.1  # Cooldown in seconds

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
        self.last_collision_time = 0

    def move(self):
        self.x += self.speed_x
        self.y += self.speed_y

        if self.y <= 0 or self.y >= SCREEN_HEIGHT - BALL_SIZE:
            self.speed_y *= -1

    def reset(self):
        self.x = SCREEN_WIDTH // 2
        self.y = SCREEN_HEIGHT // 2
        self.speed_x *= -1
        self.last_collision_time = time.time()

    def draw(self, screen):
        pygame.draw.ellipse(screen, WHITE, (self.x, self.y, BALL_SIZE, BALL_SIZE))

    def check_collision(self, paddle):
        current_time = time.time()
        if current_time - self.last_collision_time > COLLISION_COOLDOWN:
            if self.x <= paddle.x + PADDLE_WIDTH and paddle.y < self.y < paddle.y + PADDLE_HEIGHT:
                self.speed_x *= -1
                self.last_collision_time = current_time
            elif self.x + BALL_SIZE >= paddle.x and paddle.y < self.y < paddle.y + PADDLE_HEIGHT:
                self.speed_x *= -1
                self.last_collision_time = current_time

def recv_json(sock):
    buffer = ""
    while True:
        data = sock.recv(1024).decode()
        buffer += data
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            yield json.loads(line)

def handle_networking(role, paddle, opponent_paddle, ball, scores, game_state):
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
                'ball_speed_y': ball.speed_y,
                'scores': scores,
                'game_running': game_state['running']
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
            scores[0] = data['scores'][0]
            scores[1] = data['scores'][1]
            game_state['running'] = data['game_running']

def main(role):
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Ping Pong Online")
    clock = pygame.time.Clock()

    paddle = Paddle(50 if role == 'host' else SCREEN_WIDTH - 60, SCREEN_HEIGHT // 2 - PADDLE_HEIGHT // 2)
    opponent_paddle = Paddle(SCREEN_WIDTH - 60 if role == 'host' else 50, SCREEN_HEIGHT // 2 - PADDLE_HEIGHT // 2)
    ball = Ball()

    scores = [0, 0]  # [Host score, Client score]
    game_state = {'running': True}  # Control game state
    space_pressed = False  # Prevent repeated toggles on a single press

    networking_thread = threading.Thread(target=handle_networking, args=(role, paddle, opponent_paddle, ball, scores, game_state), daemon=True)
    networking_thread.start()

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        keys = pygame.key.get_pressed()

        # Host can toggle game running state
        if role == 'host':
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

            if role == 'host':
                ball.move()
                ball.check_collision(paddle)
                ball.check_collision(opponent_paddle)

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

if __name__ == "__main__":
    role = input("Enter 'host' to host the game or 'client' to join: ").strip().lower()
    main(role)
