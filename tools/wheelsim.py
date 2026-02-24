import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from scipy.interpolate import splprep, splev

# -------------------------
# CONFIGURATION
# -------------------------
offset = 0.3        # wheel axis offset from contact point
line_length = 0.4    # length of tangent line representing wheel
smoothness = 0.001   # spline smoothness (lower = more accurate)

# -------------------------
# GLOBALS
# -------------------------
drawing = False
points = []
path_ready = False

# -------------------------
# DRAWING HANDLERS
# -------------------------
def on_press(event):
    global drawing, points
    drawing = True
    points = []

def on_release(event):
    global drawing, path_ready
    drawing = False
    if len(points) > 5:
        path_ready = True
    else:
        print("Draw a longer path.")

def on_move(event):
    global points
    if drawing and event.xdata is not None and event.ydata is not None:
        points.append([event.xdata, event.ydata])
        ax.plot(event.xdata, event.ydata, 'k.', markersize=2)
        fig.canvas.draw_idle()

# -------------------------
# PLOT SETUP
# -------------------------
fig, ax = plt.subplots()
ax.set_aspect('equal')
ax.set_xlim(-5, 5)
ax.set_ylim(-5, 5)
ax.set_title("Draw your path with the mouse, then release to animate")

fig.canvas.mpl_connect('button_press_event', on_press)
fig.canvas.mpl_connect('button_release_event', on_release)
fig.canvas.mpl_connect('motion_notify_event', on_move)

# Plot objects for animation
wheel_center_point, = ax.plot([], [], 'ro')
wheel_contact_line, = ax.plot([], [], 'r-', lw=3)
path_line, = ax.plot([], [], lw=1, color='orange')

# -------------------------
# ANIMATION SETUP
# -------------------------
def init():
    wheel_center_point.set_data([], [])
    wheel_contact_line.set_data([], [])
    return wheel_center_point, wheel_contact_line

def animate_path(x_path, y_path):
    """Return animation object for a given path."""
    dx = np.gradient(x_path)
    dy = np.gradient(y_path)

    frames = len(x_path)

    def update(i):
        x = x_path[i]
        y = y_path[i]

        # Tangent direction
        theta = np.arctan2(dy[i], dx[i])

        # Normal (for wheel offset)
        nx = -np.sin(theta)
        ny =  np.cos(theta)

        # Wheel center
        wheel_cx = x + offset * nx
        wheel_cy = y + offset * ny

        # Tangent contact line
        lx1 = x + line_length * np.cos(theta)
        ly1 = y + line_length * np.sin(theta)
        lx2 = x - line_length * np.cos(theta)
        ly2 = y - line_length * np.sin(theta)

        wheel_center_point.set_data([wheel_cx], [wheel_cy])
        wheel_contact_line.set_data([lx1, lx2], [ly1, ly2])

        return wheel_center_point, wheel_contact_line

    ani = FuncAnimation(
        fig, update, init_func=init,
        frames=frames, interval=16, blit=True
    )

    return ani

# -------------------------
# MAIN LOOP
# -------------------------
plt.ion()
plt.show(block=False)

anim = None

while True:
    plt.pause(0.01)

    if path_ready:
        path_ready = False

        # Extract drawing
        P = np.array(points)
        x = P[:,0]
        y = P[:,1]

        # Fit spline for smooth toolpath
        tck, _ = splprep([x, y], s=smoothness)
        u_fine = np.linspace(0, 1, 800)
        x_smooth, y_smooth = splev(u_fine, tck)

        path_line.set_data(x_smooth, y_smooth)

        # Run animation
        anim = animate_path(x_smooth, y_smooth)

        fig.canvas.draw_idle()
