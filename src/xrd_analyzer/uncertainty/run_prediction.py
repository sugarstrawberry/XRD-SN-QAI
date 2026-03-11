"""
简化的XRD预测脚本
直接处理test_xrd_data.npy文件并调用predict_xrd_api函数
"""

import numpy as np
import torch
from HybridFeatureDataset import extract_physical_features
from dataload import get_simxrd_d_grid
from PhyNetCNN import Model
from test import predict_xrd_api

def main():
    print("XRD数据预测")
    print("=" * 40)
    
    # 1. 加载npy数据
    print("1. 加载数据...")
    try:
        intensity_data = np.load('test_xrd_data.npy')
        print(f"   ✓ 数据形状: {intensity_data.shape}")
        print(f"   ✓ 数据范围: {intensity_data.min():.2f} - {intensity_data.max():.2f}")
    except Exception as e:
        print(f"   ❌ 加载失败: {e}")
        return
    
    # 2. 获取d-spacing网格并提取物理特征
    print("\n2. 提取物理特征...")
    try:
        d_grid = get_simxrd_d_grid()  # 使用dataload.py的网格
        physical_features = extract_physical_features(d_grid, intensity_data, num_peaks=10)
        print(f"   ✓ 物理特征维度: {len(physical_features)}")
        print(f"   ✓ 特征范围: {physical_features.min():.3f} - {physical_features.max():.3f}")
    except Exception as e:
        print(f"   ❌ 特征提取失败: {e}")
        return
    
    # 3. 初始化模型
    print("\n3. 初始化模型...")
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"   使用设备: {device}")
    
    model = Model().to(device)
    model.eval()
    print("   ✓ 模型初始化完成 (使用随机权重)")
    
    # 4. 进行预测
    print("\n4. 执行预测...")
    try:
        results = predict_xrd_api(model, intensity_data, physical_features, device, T=50)
        print("   ✓ 预测完成")
    except Exception as e:
        print(f"   ❌ 预测失败: {e}")
        return
    
    # 5. 显示结果
    print("\n" + "=" * 50)
    print("预测结果")
    print("=" * 50)
    
    print(f"全局不确定性: {results['global_uncertainty']:.4f}")
    print(f"\nTop-5 空间群预测:")
    print("-" * 40)
    
    for pred in results['top_5_predictions']:
        space_group = pred['label'] + 1  # 空间群从1开始
        prob = pred['probability']
        std = pred['std_dev']
        print(f"{pred['rank']}. 空间群 {space_group:3d}: {prob:.4f} ± {std:.4f}")
    
    # 6. 保存结果
    print(f"\n保存结果到文件...")
    import json
    with open('prediction_output.json', 'w') as f:
        json.dump(results, f, indent=2)
    print("   ✓ 结果已保存到 prediction_output.json")
    
    print(f"\n" + "=" * 50)
    print("预测完成!")
    print("注意: 当前使用随机初始化的模型，如需准确结果请加载训练好的模型权重")

if __name__ == '__main__':
    main()