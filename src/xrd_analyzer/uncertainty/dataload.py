import numpy as np

def get_simxrd_d_grid(wavelength=1.5406):
    """
    获取标准的d-spacing网格
    基于10-80°的2θ角度范围，生成3501个点的d-spacing网格
    """
    angles_2theta_simxrd = np.linspace(10, 80, 3501)
    theta_rad = np.radians(angles_2theta_simxrd / 2)
    d_grid = wavelength / (2 * np.sin(theta_rad))
    return d_grid[::-1]  # 反转，从大到小排列