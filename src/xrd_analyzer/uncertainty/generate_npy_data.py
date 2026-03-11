import json
import numpy as np
from dataload import get_simxrd_d_grid

def process_xrd_json_to_npy(json_file_path, output_file='processed_xrd.npy'):
    """
    使用utils/dataload.py的方法处理XRD数据生成npy文件
    
    Parameters:
    - json_file_path: 输入JSON文件路径
    - output_file: 输出npy文件路径
    
    Returns:
    - processed_array: 处理后的一维强度数组 [3501,]
    """
    print(f"使用dataload.py方法处理: {json_file_path} -> {output_file}")
    
    # 读取JSON数据
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    two_theta = np.array(data['two_theta_values'])
    intensities = np.array(data['intensities'])
    wavelength = data.get('wavelength', 1.5406)
    
    print(f"原始数据: {len(two_theta)}个点, 2θ范围{two_theta.min():.1f}°-{two_theta.max():.1f}°")
    
    # 使用dataload.py的标准网格 (3501个点，10-80°)
    simxrd_d_grid = get_simxrd_d_grid(wavelength=wavelength)
    
    # 转换2θ到d-spacing (与dataload.py完全一致)
    theta_rad = np.radians(two_theta / 2)
    d_values = wavelength / (2 * np.sin(theta_rad))
    
    # 过滤有效数据点 (与dataload.py完全一致)
    valid_mask = (np.isfinite(d_values) & 
                  (d_values >= simxrd_d_grid.min()) & 
                  (d_values <= simxrd_d_grid.max()))
    
    d_valid = d_values[valid_mask]
    i_valid = intensities[valid_mask]
    
    print(f"有效数据: {len(d_valid)}/{len(two_theta)}个点")
    
    if len(d_valid) == 0:
        print("❌ 没有有效数据点!")
        return None
    
    # 插值到标准网格 (与dataload.py完全一致)
    interpolated = np.interp(simxrd_d_grid, d_valid[::-1], i_valid[::-1])
    
    # 归一化 (与dataload.py完全一致)
    if np.max(interpolated) > 0:
        interpolated *= 100 / np.max(interpolated)
    
    # 保存为npy文件
    np.save(output_file, interpolated)
    
    print(f"✓ 处理完成: 形状{interpolated.shape}, 范围{interpolated.min():.1f}-{interpolated.max():.1f}")
    print(f"✓ 已保存到: {output_file}")
    
    return interpolated

if __name__ == '__main__':
    # 处理test_xrd_data.json生成npy文件
    processed_data = process_xrd_json_to_npy('test_xrd_data.json', 'test_xrd_data.npy')
    
    # 验证生成的文件
    loaded_data = np.load('test_xrd_data.npy')
    print(f"\n验证: 加载的数据形状为 {loaded_data.shape}, 类型为 {loaded_data.dtype}")