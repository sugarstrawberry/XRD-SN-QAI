"""
XRD预测主程序
所有文件都在同一个文件夹中，简化导入和运行
"""

import json
import numpy as np
import torch
import os

# 本地导入
from dataload import get_simxrd_d_grid
from HybridFeatureDataset import extract_physical_features
from PhyNetCNN import Model
from test import predict_xrd_api

def main():
    print("XRD晶体结构预测系统")
    print("=" * 50)
    
    # 检查必要文件
    required_files = ['test_xrd_data.json', 'PhyNetCNN.py', 'HybridFeatureDataset.py', 'test.py', 'dataload.py']
    missing_files = [f for f in required_files if not os.path.exists(f)]
    
    if missing_files:
        print(f"❌ 缺少必要文件: {missing_files}")
        return
    
    print("✓ 所有必要文件已就绪")
    
    # 步骤1: 处理JSON数据
    print("\n步骤1: 处理JSON数据")
    print("-" * 30)
    
    try:
        with open('test_xrd_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        two_theta = np.array(data['two_theta_values'])
        intensities = np.array(data['intensities'])
        wavelength = data.get('wavelength', 1.5406)
        
        print(f"✓ 读取数据: {len(two_theta)}个点")
        
        # 使用dataload方法处理
        d_grid = get_simxrd_d_grid(wavelength=wavelength)
        
        # 转换到d-spacing
        theta_rad = np.radians(two_theta / 2)
        d_values = wavelength / (2 * np.sin(theta_rad))
        
        # 过滤和插值
        valid_mask = (np.isfinite(d_values) & 
                      (d_values >= d_grid.min()) & 
                      (d_values <= d_grid.max()))
        
        d_valid = d_values[valid_mask]
        i_valid = intensities[valid_mask]
        
        interpolated = np.interp(d_grid, d_valid[::-1], i_valid[::-1])
        if np.max(interpolated) > 0:
            interpolated *= 100 / np.max(interpolated)
        
        # 保存处理后的数据
        np.save('test_xrd_data.npy', interpolated)
        print(f"✓ 数据处理完成: {interpolated.shape}")
        
    except Exception as e:
        print(f"❌ 数据处理失败: {e}")
        return
    
    # 步骤2: 提取物理特征
    print("\n步骤2: 提取物理特征")
    print("-" * 30)
    
    try:
        intensity_data = np.load('test_xrd_data.npy')
        physical_features = extract_physical_features(d_grid, intensity_data, num_peaks=10)
        print(f"✓ 特征提取完成: {len(physical_features)}维")
        
    except Exception as e:
        print(f"❌ 特征提取失败: {e}")
        return
    
    # 步骤3: 模型预测
    print("\n步骤3: 模型预测")
    print("-" * 30)
    
    try:
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        print(f"✓ 使用设备: {device}")
        
        model = Model().to(device)
        model.eval()
        print("✓ 模型初始化完成")
        
        # 执行预测
        results = predict_xrd_api(model, intensity_data, physical_features, device, T=50)
        print("✓ 预测完成")
        
    except Exception as e:
        print(f"❌ 预测失败: {e}")
        return
    
    # 步骤4: 显示结果
    print("\n" + "=" * 50)
    print("预测结果")
    print("=" * 50)
    
    print(f"全局不确定性: {results['global_uncertainty']:.4f}")
    print(f"\nTop-5 空间群预测:")
    print("-" * 40)
    
    for pred in results['top_5_predictions']:
        space_group = pred['label'] + 1
        prob = pred['probability']
        std = pred['std_dev']
        print(f"{pred['rank']}. 空间群 {space_group:3d}: {prob:.4f} ± {std:.4f}")
    
    # 保存结果
    with open('prediction_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ 结果已保存到: prediction_results.json")
    print(f"\n预测完成! 最可能的空间群: {results['top_5_predictions'][0]['label'] + 1}")

if __name__ == '__main__':
    main()